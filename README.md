# Demo-SNIIM-Mexico

Helpful Python example for fetching and parsing sugar (`azucar`) prices from
Mexico's SNIIM website (Sistema Nacional de Informacion e Integracion de
Mercados), run by Secretaria de Economia.

## What this repository demonstrates

The script `scrape_azucar_example.py` shows an end-to-end data retrieval flow:

1. Fetch available markets from the SNIIM dropdown.
2. Build a query URL for a market and date range.
3. Download the HTML results page.
4. Parse the table data into a clean pandas DataFrame.
5. Optionally export the result to CSV.

## Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`
- `lxml`
- `pandas`

Install dependencies:

```bash
pip install requests beautifulsoup4 lxml pandas
```

## Quick start

Run with defaults (market `100`, January 2025):

```bash
python scrape_azucar_example.py
```

## Useful commands

List all market IDs available today from SNIIM:

```bash
python scrape_azucar_example.py --list-markets
```

Use a specific market ID and date range:

```bash
python scrape_azucar_example.py \
  --market-id 100 \
  --year 2025 \
  --month 01 \
  --day-start 01 \
  --day-end 31
```

Find market automatically by name text match:

```bash
python scrape_azucar_example.py --market-query "Iztapalapa"
```

Save to a custom file path:

```bash
python scrape_azucar_example.py --output data/azucar_iztapalapa_2025_01.csv
```

Preview results in console without writing CSV:

```bash
python scrape_azucar_example.py --no-save
```

## Notes

- SNIIM pages can change over time; if parsing breaks, inspect the HTML classes
  in the target tables.
- IDs and available markets come directly from the current SNIIM dropdown.