# Bali Rental Market Data

Monthly asking-price statistics for long-term rentals and villas for sale across Bali, per area,
computed from live listings on the [Livuma](https://livuma.com) marketplace. The same numbers are
published on [livuma.com/bali-rental-prices](https://livuma.com/bali-rental-prices) and served by the
public endpoint `https://livuma.com/api/public/market-stats`. This repository keeps every monthly
capture as tidy CSV so the series can be charted, joined and cited.

Licence: [CC BY 4.0](LICENSE). Use it freely, attribute "Livuma (https://livuma.com/bali-rental-prices)".

## What is in the data

| File | Rows | Unit | Since |
|---|---|---|---|
| `data/long_term_rentals.csv` | one row per area per month | IDR per month (asking rent) | 2026-09 |
| `data/villas_for_sale.csv` | one row per area per month | IDR (asking sale price) | 2026-09 |
| `data/median_monthly_rent_history.csv` | one row per area per month | IDR per month (median only) | 2026-08 |
| `data/snapshots/<period>.json` | raw API response for that month | | 2026-09 |

Areas currently covered: Berawa, Canggu, Cemagi, Jimbaran, Legian, Nusa Dua, Pererenan, Sanur,
Seminyak, Seseh, Tabanan, Ubud, Uluwatu. Kuta and Denpasar appear in the rent history for 2026-08
but fell below the publication threshold in 2026-09. An area is included in a month only when it
clears the threshold, so the set of areas can change from month to month.

## Methodology

Quoted from the API response:

> Median asking price per area; typicalRange is the 10th–90th percentile band. Areas with fewer
> than 3 listings in a category are excluded. Captured monthly.
> medianChangeVsPreviousMonthPercent is only present when the previous calendar month was captured.

Livuma captures the snapshot on the 2nd of each month at 01:30 UTC. The 10th–90th percentile range
is only published when the sample is large enough; thin samples carry a median but blank `p10_idr`
and `p90_idr`.

## Columns

`long_term_rentals.csv` and `villas_for_sale.csv`

| Column | Meaning |
|---|---|
| `period` | Capture month, `YYYY-MM` |
| `area` | Area name as shown on Livuma |
| `area_slug` | Stable key for the area, matches the URL slug on livuma.com |
| `listings` | Number of live listings the statistics were computed from |
| `median_idr` | Median asking price in Indonesian rupiah. Monthly rent for rentals, sale price for villas |
| `p10_idr` | 10th percentile of asking prices, blank when the sample is too small |
| `p90_idr` | 90th percentile of asking prices, blank when the sample is too small |
| `median_change_vs_previous_month_pct` | Change of the median versus the previous captured month, in percent, blank when there is no previous month for that area |
| `captured_at_utc` | Timestamp of the snapshot the row came from |

`median_monthly_rent_history.csv`

| Column | Meaning |
|---|---|
| `period` | Month, `YYYY-MM` |
| `area`, `area_slug` | As above |
| `median_monthly_rent_idr` | Median asking monthly rent. This is the API's rent history series, which reaches further back than the full tables and covers rentals only |

## Refresh cadence

A GitHub Actions workflow runs on the 4th of every month and on manual dispatch. It calls the
public endpoint, appends the new month, stores the raw snapshot and commits. Rows are keyed on
`(period, area_slug)`, so re-running never duplicates data. To refresh locally:

```bash
python scripts/fetch_market_stats.py
```

The script uses only the Python standard library.

## Usage

Python, standard library only:

```python
import csv
from collections import defaultdict

rent = defaultdict(dict)
with open("data/long_term_rentals.csv", newline="", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        rent[row["area"]][row["period"]] = int(row["median_idr"])

for area, by_month in sorted(rent.items()):
    latest = max(by_month)
    print(f"{area:12} {latest}  IDR {by_month[latest]:,}/month")
```

pandas:

```python
import pandas as pd
df = pd.read_csv("data/long_term_rentals.csv")
df.pivot(index="period", columns="area", values="median_idr").plot()
```

SQL (DuckDB, SQLite with the CSV loaded, or similar):

```sql
SELECT area, median_idr / 1e6 AS median_million_idr, listings
FROM long_term_rentals
WHERE period = '2026-09'
ORDER BY median_idr DESC;
```

## Known limitations

- These are asking prices from listings, not closed deals or signed contracts. Actual rents and
  sale prices are typically negotiated below the asking price.
- An area needs at least 3 live listings to be published at all, and a larger sample before the
  percentile range is published. Areas with a handful of listings move a lot month to month:
  Legian shows a +228 % rent median change in 2026-09 on four listings, which is sample noise, not
  a market move.
- The data reflects what is listed on one marketplace. Coverage grows over time, so early months
  have fewer areas and smaller samples than later ones, and month-on-month changes partly reflect
  changes in the listing mix (survivorship: listings that rent out quickly leave the sample).
- Rentals and sales are separate populations. `villas_for_sale.csv` covers villas only, not land
  or apartments.
- The history file goes back further than the full tables because the API exposes a longer
  median-rent series than it does full per-area statistics.

## Citation

Livuma, "Bali Rental Market Data", https://github.com/Livuma/bali-rental-market-data, retrieved
<date>. Underlying figures: https://livuma.com/bali-rental-prices.

A machine-readable citation is in [`CITATION.cff`](CITATION.cff).

## About Livuma

Livuma is Bali's marketplace for long-term rentals and property, built as an alternative to Airbnb
and Booking.com for people who stay for months, not nights: about half the host fees, zero guest
fees, monthly and yearly rent on automated payments, KYC-verified profiles. The same listing data
is available to AI agents through the public API at `https://livuma.com/api/public` and the MCP
server at `https://livuma.com/mcp`. Operated by PT Livuma Home Market, Badung, Bali.
