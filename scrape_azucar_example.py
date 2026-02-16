"""
Scraping Sugar (Azúcar) Prices from Mexico's SNIIM
===================================================

A self-contained example that shows, step by step, how to extract
sugar price data from the SNIIM (Sistema Nacional de Información e
Integración de Mercados) website run by Mexico's Secretaría de Economía.

The script does three things:
  1. Discovers available markets from the search page.
  2. Fetches sugar price data for a chosen market and date range.
  3. Parses the HTML response into a clean pandas DataFrame.

No external framework is needed beyond requests, beautifulsoup4, lxml,
and pandas — all standard data-science staples.

URLs
----
- Search page : https://www.economia-sniim.gob.mx/Sniim-anANT/e_SelAzu.asp
- Results page: https://www.economia-sniim.gob.mx/Sniim-anANT/e_Azucar03.asp
"""

import requests
import pandas as pd
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urlencode

# ── Configuration ────────────────────────────────────────────────────────────

SEARCH_URL = "https://www.economia-sniim.gob.mx/Sniim-anANT/e_SelAzu.asp"
RESULTS_URL = "https://www.economia-sniim.gob.mx/Sniim-anANT/e_Azucar03.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "es-MX,es;q=0.9",
}

DEFAULT_MARKET_ID = "100"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and parse sugar (azucar) prices from SNIIM Mexico."
    )
    parser.add_argument(
        "--market-id",
        default=DEFAULT_MARKET_ID,
        help=f"Market ID from SNIIM dropdown (default: {DEFAULT_MARKET_ID}).",
    )
    parser.add_argument(
        "--market-query",
        default="",
        help="Optional text to auto-find a market by name (e.g. 'Iztapalapa').",
    )
    parser.add_argument("--year", default="2025", help="Year (YYYY), e.g. 2025")
    parser.add_argument("--month", default="01", help="Month (MM), e.g. 01")
    parser.add_argument("--day-start", default="01", help="Start day (DD), e.g. 01")
    parser.add_argument("--day-end", default="31", help="End day (DD), e.g. 31")
    parser.add_argument(
        "--output",
        default="azucar_example.csv",
        help="Output CSV path (ignored when --no-save is used).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save results to CSV.",
    )
    parser.add_argument(
        "--list-markets",
        action="store_true",
        help="Only print available markets and exit.",
    )
    return parser.parse_args()


# ── Step 1: Discover available markets ───────────────────────────────────────

def fetch_markets() -> list[dict]:
    """
    Scrape the search page to get the list of markets (destinos)
    from the <select name="mercado"> dropdown.

    Returns a list of dicts: [{"id": "100", "label": "DF: Central de …"}, …]
    """
    response = requests.get(SEARCH_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    select = soup.find("select", {"name": "mercado"})

    if not select:
        raise RuntimeError("Could not find the 'mercado' <select> on the page")

    markets = []
    for option in select.find_all("option"):
        value = option.get("value", "").strip()
        label = option.get_text(strip=True)
        # Skip the placeholder option ("Todos" with value -1)
        if value and value != "-1":
            markets.append({"id": value, "label": label})

    return markets


def resolve_market_id(markets: list[dict], market_id: str, market_query: str) -> str:
    """
    Pick a market ID.
    - If --market-query is provided, try to match it in market labels.
    - Otherwise use --market-id.
    """
    if market_query:
        query = market_query.strip().lower()
        matches = [m for m in markets if query in m["label"].lower()]
        if not matches:
            raise ValueError(f"No market matched query: {market_query!r}")
        chosen = matches[0]
        print(f"Matched market from query '{market_query}': {chosen['id']} - {chosen['label']}")
        return chosen["id"]

    valid_ids = {m["id"] for m in markets}
    if market_id not in valid_ids:
        raise ValueError(
            f"market-id {market_id!r} was not found in current SNIIM market list. "
            "Run with --list-markets to inspect valid IDs."
        )
    return market_id


# ── Step 2: Build the query URL and fetch the results page ───────────────────

def build_query_url(
    mercado_id: str,
    dia_inicio: str = "01",
    dia_fin: str = "31",
    mes: str = "01",
    anio: str = "2025",
) -> str:
    """
    Construct the full results URL with query parameters.

    The SNIIM azúcar endpoint expects:
      - producto : product filter (1 = Todos)
      - ingenio  : sugar mill filter (1 = Todos)
      - mercado  : market id
      - dia1     : start day
      - dia2     : end day
      - mes      : month (two digits)
      - anio     : year
      - detalle  : "S" for detailed view
    """
    params = {
        "producto": "1",       # Todos los productos
        "ingenio": "1",        # Todos los ingenios
        "mercado": mercado_id,
        "dia1": dia_inicio,
        "dia2": dia_fin,
        "mes": mes,
        "anio": anio,
        "detalle": "S",
        "x": "45",
        "y": "15",
    }
    return f"{RESULTS_URL}?{urlencode(params)}"


def fetch_results_page(url: str) -> str:
    """GET the results page and return raw HTML."""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


# ── Step 3: Parse the HTML into a DataFrame ──────────────────────────────────

def parse_azucar_html(html: str) -> pd.DataFrame:
    """
    Parse the SNIIM azúcar results page.

    The page contains one or more <table border="1"> blocks, each with:
      - An "encabDES" cell  → market name
      - An "encabTIP" cell  → product type (e.g. "Azúcar Estándar")
      - An "encabTAB" row   → column headers (Fecha, Ingenio, Precio)
      - "Datos" / "DatosNum" cells → the actual data rows
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", {"border": "1"})

    all_rows: list[dict] = []

    for table in tables:
        # ── Extract metadata from the table header ──
        market_cell = table.find("td", {"class": "encabDES"})
        if not market_cell:
            continue
        market_name = market_cell.get_text(strip=True)

        product_cell = table.find("td", {"class": "encabTIP"})
        product_type = product_cell.get_text(strip=True) if product_cell else "Desconocido"

        # ── Find the header row (cells with class "encabTAB") ──
        header_row = None
        for row in table.find_all("tr"):
            if row.find("td", {"class": "encabTAB"}):
                header_row = row
                break

        if not header_row:
            continue

        col_names = [
            " ".join(cell.get_text(strip=True).split())
            for cell in header_row.find_all("td", {"class": "encabTAB"})
        ]

        # ── Extract data rows ──
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], class_=["Datos", "DatosNum"])
            if len(cells) < 3:
                continue

            values = [cell.get_text(strip=True) for cell in cells[:3]]
            record = dict(zip(col_names, values))
            record["Mercado"] = market_name
            record["Tipo Producto"] = product_type
            all_rows.append(record)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # ── Light cleaning ──
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")

    if "Precio encuestado" in df.columns:
        df["Precio encuestado"] = (
            df["Precio encuestado"]
            .str.replace(",", "", regex=False)
            .astype(float)
        )

    return df


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # 1. Discover markets
    print("Fetching available markets from SNIIM…")
    markets = fetch_markets()
    print(f"Found {len(markets)} markets.\n")

    # Show the first few
    for m in markets[:5]:
        print(f"  id={m['id']:>4}  {m['label']}")
    if len(markets) > 5:
        print(f"  … and {len(markets) - 5} more\n")

    if args.list_markets:
        print("\nComplete market list:")
        for m in markets:
            print(f"  id={m['id']:>4}  {m['label']}")
        return

    # 2. Pick a market and date range
    #    We'll use "DF: Central de Abasto de Iztapalapa DF" (id=100)
    #    and January 2025 as an example.
    mercado_id = resolve_market_id(markets, args.market_id, args.market_query)
    mes, anio = args.month, args.year

    url = build_query_url(
        mercado_id,
        dia_inicio=args.day_start,
        dia_fin=args.day_end,
        mes=mes,
        anio=anio,
    )
    print(f"Query URL:\n  {url}\n")

    # 3. Fetch and parse
    print("Fetching results…")
    html = fetch_results_page(url)
    df = parse_azucar_html(html)

    if df.empty:
        print("No data returned for this query.")
        return

    print(f"Got {len(df)} rows × {len(df.columns)} columns\n")
    print(df.to_string(index=False, max_rows=20))

    # 4. (Optional) Save to CSV
    if not args.no_save:
        df.to_csv(args.output, index=False)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
