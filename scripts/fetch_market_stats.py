#!/usr/bin/env python3
"""Fetch Livuma's public Bali market statistics and append new periods to the CSVs.

Source: https://livuma.com/api/public/market-stats (public, no key, rate-limited).
Stdlib only. Idempotent: rows are keyed on (period, area_slug); re-running for a period
that is already present adds nothing.

Usage:
    python scripts/fetch_market_stats.py            # fetch live and update data/
    python scripts/fetch_market_stats.py FILE.json  # ingest a saved snapshot instead of fetching
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from pathlib import Path

ENDPOINT = "https://livuma.com/api/public/market-stats"
USER_AGENT = "bali-rental-market-data/1.0 (+https://github.com/Livuma/bali-rental-market-data)"

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAPSHOTS = DATA / "snapshots"

# API array name -> CSV file name
PAGE_TYPES = {
    "longTermRentals": "long_term_rentals.csv",
    "villasForSale": "villas_for_sale.csv",
}
ROW_COLUMNS = [
    "period",
    "area",
    "area_slug",
    "listings",
    "median_idr",
    "p10_idr",
    "p90_idr",
    "median_change_vs_previous_month_pct",
    "captured_at_utc",
]
HISTORY_FILE = "median_monthly_rent_history.csv"
HISTORY_COLUMNS = ["period", "area", "area_slug", "median_monthly_rent_idr"]


def fetch() -> dict:
    req = urllib.request.Request(ENDPOINT, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fmt_number(value):
    """Write integers without a trailing .0, keep decimals otherwise, blanks for null."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["period"], r["area_slug"]))


def merge_page_type(payload: dict, json_key: str, file_name: str) -> int:
    period = payload["latestPeriod"]
    captured = payload.get("capturedAtUtc", "")
    path = DATA / file_name
    existing = read_csv(path)
    seen = {(r["period"], r["area_slug"]) for r in existing}
    added = 0
    for item in payload.get(json_key, []):
        key = (period, item["areaSlug"])
        if key in seen:
            continue
        existing.append(
            {
                "period": period,
                "area": item["area"],
                "area_slug": item["areaSlug"],
                "listings": fmt_number(item.get("listings")),
                "median_idr": fmt_number(item.get("median")),
                "p10_idr": fmt_number(item.get("typicalRangeLow")),
                "p90_idr": fmt_number(item.get("typicalRangeHigh")),
                "median_change_vs_previous_month_pct": fmt_number(item.get("medianChangeVsPreviousMonthPercent")),
                "captured_at_utc": captured,
            }
        )
        seen.add(key)
        added += 1
    write_csv(path, ROW_COLUMNS, sort_rows(existing))
    return added


def merge_history(payload: dict) -> int:
    """The API also returns up to 13 months of median monthly rent per area (rentals only)."""
    history = (payload.get("history") or {}).get("medianMonthlyRentByArea") or {}
    names = {item["areaSlug"]: item["area"] for item in payload.get("longTermRentals", [])}
    names.update({item["areaSlug"]: item["area"] for item in payload.get("villasForSale", [])})
    path = DATA / HISTORY_FILE
    existing = read_csv(path)
    known_names = {r["area_slug"]: r["area"] for r in existing if r.get("area")}
    seen = {(r["period"], r["area_slug"]) for r in existing}
    added = 0
    for slug, by_period in history.items():
        area = names.get(slug) or known_names.get(slug) or slug.replace("-", " ").title()
        for period, median in by_period.items():
            key = (period, slug)
            if key in seen:
                continue
            existing.append(
                {"period": period, "area": area, "area_slug": slug, "median_monthly_rent_idr": fmt_number(median)}
            )
            seen.add(key)
            added += 1
    write_csv(path, HISTORY_COLUMNS, sort_rows(existing))
    return added


def save_snapshot(payload: dict) -> Path:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOTS / f"{payload['latestPeriod']}.json"
    if not path.exists():
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        source = argv[1]
    else:
        payload = fetch()
        source = ENDPOINT

    period = payload["latestPeriod"]
    snapshot = save_snapshot(payload)
    added = {file_name: merge_page_type(payload, json_key, file_name) for json_key, file_name in PAGE_TYPES.items()}
    added[HISTORY_FILE] = merge_history(payload)

    print(f"source:   {source}")
    print(f"period:   {period} (captured {payload.get('capturedAtUtc', '?')})")
    print(f"snapshot: {snapshot.relative_to(ROOT)}")
    for file_name, count in added.items():
        total = len(read_csv(DATA / file_name))
        print(f"{file_name}: +{count} rows (now {total})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
