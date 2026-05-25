"""
Scale Scraper — combina datele din produse_campanie.csv cu istoricul de pe
istoric-preturi.info si produce un CSV de analiza.

Flux per produs:
  1. Cauta URL-ul eMAG pe istoric-preturi.info (via search input + redirect)
  2. Asteapta canvas-ul Chart.js
  3. Extrage pretul minim eMAG din ultimele 14 zile
  4. Calculeaza price_change_pct fata de pretul din campanie
  5. Scrie rezultatul in CSV

Edge cases gestionate:
  - Produs negasit pe istoric-preturi.info  → not_found
  - Nicio inregistrare eMAG in fereastra     → no_data
  - Eroare de retea / timeout               → error

"""

import csv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


INPUT_CSV        = "produse_campanie.csv"
OUTPUT_CSV       = "analiza_preturi.csv"
ZILE_REFERINTA   = 14
MAGAZIN_TINTA    = "eMAG"
DELAY_INTRE_PROD = 2.0   # secunde pauza intre produse
TIMEOUT_PAGINA   = 30000 # ms

OUTPUT_FIELDS = [
    "product_id", "offer_id", "name", "category",
    "price_emag_ron", "lowest_price_emag_ron", "lowest_price_date",
    "price_change_pct", "istoric_url", "status", "url"
]


LUNI_RO = {
    "Ian": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr",
    "Mai": "May", "Iun": "Jun", "Iul": "Jul", "Aug": "Aug",
    "Sep": "Sep", "Oct": "Oct", "Noi": "Nov", "Dec": "Dec"
}

def parse_date(label: str) -> datetime | None:
    normalized = label.strip()
    for ro, en in LUNI_RO.items():
        if ro in normalized:
            normalized = normalized.replace(ro, en)
            break
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def get_istoric_url(page, emag_url: str) -> str | None:
    """
    Introduce URL-ul eMAG in search-ul de pe istoric-preturi.info
    si returneaza URL-ul paginii de produs dupa redirect.
    Returneaza None daca produsul nu e gasit.
    """
    try:
        page.goto("https://www.istoric-preturi.info/", wait_until="domcontentloaded", timeout=TIMEOUT_PAGINA)
        page.wait_for_timeout(1000)

        search_input = page.query_selector(".mainSearchField")
        if not search_input:
            print("    WARN: .mainSearchField negasit")
            return None
        search_input.click()
        page.wait_for_timeout(200)
        search_input.fill(emag_url)
        page.wait_for_timeout(300)
 
        val = search_input.input_value()
        if not val:
            print("    WARN: fill() nu a functionat, incerc type()")
            search_input.type(emag_url, delay=20)
            page.wait_for_timeout(300)

        page.query_selector("button[onclick*='searchStart']").click()

        try:
            page.wait_for_url("**/pd/**", timeout=8000)
            return page.url
        except PWTimeout:
            not_found_msg = page.query_selector("text=Nu putem gasi produsul")
            if not_found_msg:
                return None
            current = page.url
            if "/pd/" in current:
                return current
            return None

    except PWTimeout:
        return None
    except Exception as e:
        print(f"    WARN get_istoric_url: {e}")
        return None


def get_chart_data(page) -> dict | None:
    """Extrage datele din instanta Chart.js de pe pagina curenta."""
    try:
        page.wait_for_function(
            "() => typeof Chart !== 'undefined' && Object.keys(Chart.instances).length > 0",
            timeout=12000
        )
    except PWTimeout:
        return None

    data = page.evaluate("""
        () => {
            const keys = Object.keys(Chart.instances);
            if (!keys.length) return null;
            const instance = Chart.instances[keys[0]];
            if (!instance) return null;
            return {
                labels: instance.data.labels,
                datasets: instance.data.datasets.map(ds => ({
                    label: ds.label,
                    data: ds.data
                }))
            };
        }
    """)
    return data


def extract_min_price(chart_data: dict, magazin: str, zile: int) -> dict:
    labels   = chart_data.get("labels", [])
    datasets = chart_data.get("datasets", [])

    target = next(
        (ds for ds in datasets if ds["label"].strip().lower() == magazin.lower()),
        None
    )
    if not target:
        available = [ds["label"] for ds in datasets]
        return {"status": "no_data", "detail": f"'{magazin}' negasit. Disponibile: {available}"}

    cutoff = datetime.now() - timedelta(days=zile)
    window = []
    for label, price in zip(labels, target["data"]):
        if price is None:
            continue
        dt = parse_date(label)
        if dt and dt >= cutoff:
            window.append({"data": label, "pret": float(price)})

    if not window:
        return {"status": "no_data", "detail": f"Nicio inregistrare in ultimele {zile} zile"}

    best = min(window, key=lambda x: x["pret"])
    return {
        "status":       "ok",
        "lowest_price": best["pret"],
        "lowest_date":  best["data"]
    }


def process_product(page, row: dict) -> dict:
    emag_url     = row["url"]
    price_campanie = float(row["price_ron"]) if row.get("price_ron") else None

    result = {
        "product_id":           row.get("product_id", ""),
        "offer_id":             row.get("offer_id", ""),
        "name":                 row.get("name", ""),
        "category":             row.get("category", ""),
        "price_emag_ron":       price_campanie,
        "lowest_price_emag_ron": None,
        "lowest_price_date":    None,
        "price_change_pct":     None,
        "istoric_url":          None,
        "status":               "error",
        "url":                  emag_url
    }

    istoric_url = get_istoric_url(page, emag_url)
    if not istoric_url:
        result["status"] = "not_found"
        return result

    result["istoric_url"] = istoric_url

    chart_data = get_chart_data(page)
    if not chart_data:
        result["status"] = "chart_error"
        return result

    price_result = extract_min_price(chart_data, MAGAZIN_TINTA, ZILE_REFERINTA)
    result["status"] = price_result["status"]

    if price_result["status"] == "ok":
        lowest = price_result["lowest_price"]
        result["lowest_price_emag_ron"] = lowest
        result["lowest_price_date"]     = price_result["lowest_date"]

        if price_campanie and lowest:
            pct = ((price_campanie - lowest) / lowest) * 100
            result["price_change_pct"] = round(pct, 2)

    return result


def main():
    if not Path(INPUT_CSV).exists():
        print(f"EROARE: '{INPUT_CSV}' nu exista. Ruleaza mai intai emag_scraper.py")
        return

    with open(INPUT_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Produse de procesat: {len(rows)}")
    print(f"Output: {OUTPUT_CSV}\n")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page    = context.new_page()

        for i, row in enumerate(rows, 1):
            name_short = row.get("name", "")[:55]
            print(f"[{i}/{len(rows)}] {name_short}...")

            try:
                result = process_product(page, row)
            except Exception as e:
                print(f"  EROARE neasteptata: {e}")
                result = {f: row.get(f, "") for f in OUTPUT_FIELDS}
                result["status"] = f"error: {e}"

            results.append(result)

            status = result["status"]
            if status == "ok":
                print(f"  ✓ campanie={result['price_emag_ron']} RON | "
                      f"min14z={result['lowest_price_emag_ron']} RON | "
                      f"delta={result['price_change_pct']}%")
            else:
                print(f"  ✗ {status}")

            if i < len(rows):
                time.sleep(DELAY_INTRE_PROD)

        browser.close()

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    ok       = sum(1 for r in results if r["status"] == "ok")
    no_data  = sum(1 for r in results if r["status"] == "no_data")
    notfound = sum(1 for r in results if r["status"] == "not_found")
    errors   = len(results) - ok - no_data - notfound

    print(f"\n{'='*50}")
    print(f"Sumar: {ok} ok | {no_data} fara date | {notfound} negasite | {errors} erori")
    print(f"Rezultate salvate in '{OUTPUT_CSV}'")

if __name__ == "__main__":
    main()