"""
eMAG Campaign Scraper
Extrage produsele dintr-o pagina de campanie eMAG si le salveaza intr-un CSV.

"""

import requests
import csv
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urlencode

BASE_URL = "https://www.emag.ro/label/EW---Laptopuri"
PARAMS = {
    "ref_label_campaign": "electro-weekend-22-25-mai-2026_laptopuri",
    "rec[source]": "label-campaign",
}
OUTPUT_FILE = "produse_campanie.csv"
DELAY_BETWEEN_PAGES = 1.5 

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ro-RO,ro;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_products(soup):
    """Extrage produsele dintr-un obiect BeautifulSoup al paginii."""
    products = []
    cards = soup.select("div.card-item.js-product-data")

    for card in cards:
        name = card.get("data-name", "").strip()
        url = card.get("data-url", "").strip()
        product_id = card.get("data-product-id", "")
        offer_id = card.get("data-offer-id", "")
        category = card.get("data-category-name", "").strip()

        price = None
        raw_product = card.get("data-product", "")
        if raw_product:
            try:
                product_json = json.loads(raw_product)
                price = product_json.get("price")
            except json.JSONDecodeError:
                pass

        if price is None:
            price_el = card.select_one("p.product-new-price")
            if price_el:
                raw = price_el.get_text(separator="").replace("Lei", "").replace("\xa0", "").strip()
                raw = raw.replace(".", "").replace(",", ".")
                try:
                    price = float(raw)
                except ValueError:
                    price = None

        if name and url:
            products.append({
                "product_id": product_id,
                "offer_id": offer_id,
                "name": name,
                "category": category,
                "price_ron": price,
                "url": url,
            })

    return products


def build_page_url(base_url, page, params):
    """Construieste URL-ul pentru pagina N.
    Pagina 1: /label/EW---Laptopuri?...
    Pagina 3: /label/EW---Laptopuri/p3?...
    """
    if page == 1:
        return f"{base_url}?{urlencode(params)}"
    return f"{base_url}/p{page}?{urlencode(params)}"


def has_products(soup):
    """Verifica daca pagina contine produse."""
    return bool(soup.select("div.card-item.js-product-data"))


def scrape_campaign(base_url, params):
    """Parcurge toate paginile campaniei si returneaza lista de produse."""
    all_products = []
    page = 1

    while True:
        url = build_page_url(base_url, page, params)
        print(f"  Pagina {page}: {url}")
 
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  Eroare la request: {e}")
            break
 
        soup = BeautifulSoup(resp.text, "html.parser")
        products = parse_products(soup)
 
        if not products:
            print(f"  Niciun produs gasit pe pagina {page}, oprire.")
            break
 
        all_products.extend(products)
        print(f"  {len(products)} produse extrase (total: {len(all_products)})")
 
        if len(products) < 60:
            print("  Pagina incompleta — ultima pagina reala, oprire.")
            break
 
        page += 1
        time.sleep(DELAY_BETWEEN_PAGES)
 
    return all_products





def save_to_csv(products, filename):
    """Salveaza lista de produse intr-un fisier CSV."""
    if not products:
        print("Niciun produs de salvat.")
        return

    fieldnames = ["product_id", "offer_id", "name", "category", "price_ron", "url"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)

    print(f"\nSalvat {len(products)} produse in '{filename}'")



if __name__ == "__main__":
    print(f"Scraping campanie eMAG: {BASE_URL}\n")
    products = scrape_campaign(BASE_URL, PARAMS)
    save_to_csv(products, OUTPUT_FILE)

    print("\nPrimele 3 produse:")
    for p in products[:3]:
        print(f"  - {p['name'][:60]}...")
        print(f"    Pret: {p['price_ron']} RON")
        print(f"    URL: {p['url'][:80]}...")