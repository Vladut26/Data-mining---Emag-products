# E-commerce Price Manipulation Analysis

## Hypothesis

Online retailers inflate product prices before making discount vouchers or
promotional codes available, so that the nominal discount is partially or
entirely artificial.

Specifically, the project investigates whether eMAG (Romania's largest online
retailer) raises listed prices ahead of promotional campaigns, such that the
voucher applied at checkout merely offsets a recent price increase rather than
offering a genuine saving.

---

## Methodology

### 1. Campaign product collection (`emag_scraper.py`)

A Python script scrapes the eMAG campaign page for an active promotion
(e.g. *Electro Weekend 22–25 May 2026*) and collects all listed products.

- Iterates through paginated results using the `/pN` URL pattern
- Extracts per-product: name, category, current listed price, product URL,
  product ID, and offer ID
- Stops automatically when a page returns fewer than 60 products (the last
  real page), preventing re-pagination loops
- Output: `produse_campanie.csv`

### 2. Historical price retrieval (`scale_scraper.py`)

For each product in the campaign CSV, the script retrieves its 6-month price
history from [istoric-preturi.info](https://www.istoric-preturi.info) — a
Romanian price tracking aggregator covering eMAG, Altex, evoMAG, and hundreds
of other retailers.

- Uses Playwright to automate a real Chromium browser, because price history
  data is rendered client-side via an obfuscated Chart.js instance (the raw
  data blob is encrypted and decoded at runtime — no static API endpoint exists)
- Submits each eMAG product URL to the site's search form and follows the
  redirect to the product's history page
- Waits for the Chart.js instance to initialize, then reads price data directly
  from `Chart.instances` in browser memory
- Extracts the **minimum eMAG price over the past 14 days** as the reference
  price
- Handles edge cases: product not found in the database, no eMAG entries in
  the time window, page load timeouts
- Output: `analiza_preturi.csv`

### 3. Analysis output

The final CSV contains the following fields per product:

| Field | Description |
|---|---|
| `product_id` | eMAG internal product ID |
| `offer_id` | eMAG offer ID |
| `name` | Product name |
| `category` | Product category |
| `price_emag_ron` | Listed price during the campaign (RON) |
| `lowest_price_emag_ron` | Minimum eMAG price in the past 14 days (RON) |
| `lowest_price_date` | Date of the lowest recorded price |
| `price_change_pct` | % change: campaign price vs. 14-day minimum |
| `istoric_url` | URL of the product's history page |
| `status` | `ok`, `not_found`, `no_data`, `chart_error`, or `error` |
| `url` | Original eMAG product URL |

A **positive `price_change_pct`** means the campaign price is higher than the
lowest price in the two weeks prior — consistent with the hypothesis that prices
were inflated before the voucher was made available.

---

## Data Sources

- **eMAG.ro** — product listings and campaign pages (public HTML, parsed via
  BeautifulSoup)
- **istoric-preturi.info** — historical price tracker covering 40M+ products
  from 500+ Romanian retailers; price data extracted via Playwright from the
  Chart.js runtime instance

---

## Technical Stack

| Tool | Purpose |
|---|---|
| Python 3.12 | Core language |
| `requests` + `BeautifulSoup` | eMAG HTML parsing |
| `Playwright` (Chromium) | JavaScript-rendered price history extraction |
| `csv` | Data I/O |
| `datetime` | 14-day rolling window filtering |

---

## Limitations

- **Historic-preturi.info coverage** — not all products have sufficient price
  history; newer or niche products may return `not_found` or `no_data`
- **Sampling window** — the 14-day reference window may not capture price
  increases that occurred more than two weeks before the campaign
- **Single campaign** — results are specific to the analysed promotion; broader
  conclusions would require data across multiple campaigns and categories
- **Correlation vs. causation** — a price increase before a voucher campaign
  is consistent with the hypothesis but does not by itself prove intentional
  manipulation