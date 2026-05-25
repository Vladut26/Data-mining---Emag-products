"""
Istoric Preturi Scraper - versiune debug
Extrage istoricul de preturi de pe istoric-preturi.info pentru un produs.

"""

from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import json


TEST_URL = (
    "https://www.istoric-preturi.info/pd/63475017/83J2001XRM/"
    "laptop-lenovo-ideapad-slim-5-13arp10-13-3-quot-wuxga-1920x1200-ips-400nits-"
    "anti-glare-100-srgb-amd-ryzen-trade-5-7535hs-6c-12t-3-3-4-55ghz-3mb-l2-16mb-"
    "l3-video-integrated-amd-radeon-trade-660m-graphics-ram-1x-16gb-soldered-"
    "lpddr5x-6400-ssd-1tb-ss?q=ultimele6luni"
)

ZILE_REFERINTA = 14
MAGAZIN_TINTA  = "eMAG"



def get_chart_data(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("  Incarcare pagina...")
        page.goto(url, wait_until="networkidle", timeout=30000)

        debug = page.evaluate("""
            () => ({
                chartDefined:  typeof Chart !== 'undefined',
                chartVersion:  typeof Chart !== 'undefined' ? Chart.version : null,
                instanceKeys:  typeof Chart !== 'undefined' ? Object.keys(Chart.instances) : [],
                canvasExists:  !!document.getElementById('pricesChart'),
            })
        """)
        print(f"  DEBUG: {json.dumps(debug, indent=4)}")

        if not debug["chartDefined"]:
            print("  EROARE: Chart.js nu e definit pe pagina.")
            browser.close()
            return {}

        data = None

        if debug["instanceKeys"]:
            # Chart.js v2 — instante in Chart.instances
            key = debug["instanceKeys"][0]
            print(f"  Chart.js v2 — folosesc instanta: '{key}'")
            data = page.evaluate("""
                () => {
                    const keys = Object.keys(Chart.instances);
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
        else:
            # Chart.js v3+ — instanta pe canvas
            print("  Chart.instances gol — incerc Chart.js v3+ via canvas...")
            data = page.evaluate("""
                () => {
                    const canvas = document.getElementById('pricesChart');
                    if (!canvas) return null;
                    const instance = canvas.__chartjs__
                                  || canvas._chart
                                  || (typeof Chart !== 'undefined' && Chart.getChart && Chart.getChart(canvas));
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

        print(f"  Date extrase: {'OK - ' + str(len(data.get('labels',[]))) + ' labels' if data else 'null'}")
        browser.close()
        return data or {}


# ── Procesare date ────────────────────────────────────────────────────────────

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
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def extract_min_price(chart_data: dict, magazin: str, zile: int) -> dict:
    if not chart_data:
        return {"error": "Date indisponibile"}

    labels   = chart_data.get("labels", [])
    datasets = chart_data.get("datasets", [])

    target_dataset = None
    available = []
    for ds in datasets:
        available.append(ds["label"])
        if ds["label"].strip().lower() == magazin.strip().lower():
            target_dataset = ds
            break

    if not target_dataset:
        return {
            "error": f"Magazinul '{magazin}' nu a fost gasit",
            "magazine_disponibile": available
        }

    cutoff = datetime.now() - timedelta(days=zile)
    prices_in_window = []

    for label, price in zip(labels, target_dataset["data"]):
        if price is None:
            continue
        date = parse_date(label)
        if date and date >= cutoff:
            prices_in_window.append({"data": label, "pret": price})

    if not prices_in_window:
        return {
            "error": f"Nicio inregistrare pentru '{magazin}' in ultimele {zile} zile",
            "total_inregistrari": len(target_dataset["data"])
        }

    min_entry = min(prices_in_window, key=lambda x: x["pret"])

    return {
        "magazin":         magazin,
        "zile_analizate":  zile,
        "pret_minim_ron":  min_entry["pret"],
        "data_pret_minim": min_entry["data"],
        "nr_inregistrari": len(prices_in_window),
        "toate_preturile": prices_in_window
    }



if __name__ == "__main__":
    print(f"Test extragere istoric preturi\n{'='*50}")
    print(f"URL: {TEST_URL[:80]}...\n")

    chart_data = get_chart_data(TEST_URL)

    if not chart_data:
        print("Nu s-au putut extrage datele.")
        exit(1)

    print(f"\nMagazine gasite in grafic:")
    for ds in chart_data["datasets"]:
        non_null = [x for x in ds["data"] if x is not None]
        print(f"  - '{ds['label']}': {len(non_null)} inregistrari")

    print(f"\nAnaliza pret {MAGAZIN_TINTA} din ultimele {ZILE_REFERINTA} zile:")
    result = extract_min_price(chart_data, MAGAZIN_TINTA, ZILE_REFERINTA)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    with open("chart_data_raw.json", "w", encoding="utf-8") as f:
        json.dump(chart_data, f, indent=2, ensure_ascii=False)
    print(f"\nDate brute salvate in 'chart_data_raw.json'")