"""Download raw inputs into data/raw (gitignored). Registers every file in a lineage manifest.

Usage:
    uv run python scripts/download.py eia-hourly --year 2024 [--respondent ERCO]
    uv run python scripts/download.py eia-facets

Requires EIA_API_KEY in .env (free key from https://www.eia.gov/opendata/). The key is read via
efuel_ci.config.Settings and never printed. Output: data/raw/eia_<respondent>_fueltype_<year>.csv
(long format: period, respondent, fueltype, type-name, value, value-units) plus a .manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

from efuel_ci.config import REPO_ROOT, get_settings
from efuel_ci.lineage import Manifest

BASE = "https://api.eia.gov/v2/electricity/rto/fuel-type-data"
PAGE = 5000
FIELDS = [
    "period",
    "respondent",
    "respondent-name",
    "fueltype",
    "type-name",
    "value",
    "value-units",
]


def _get(url: str, params: dict, key: str, retries: int = 4) -> dict:
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params={**params, "api_key": key}, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt >= retries:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def fetch_year(year: int, respondent: str, key: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    params = {
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": respondent,
        "start": f"{year}-01-01T00",
        "end": f"{year}-12-31T23",
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": PAGE,
    }
    while True:
        doc = _get(f"{BASE}/data/", {**params, "offset": offset}, key)
        data = doc.get("response", {}).get("data", [])
        rows.extend(data)
        total = int(doc.get("response", {}).get("total", 0))
        offset += PAGE
        print(f"  fetched {len(rows)}/{total}", file=sys.stderr)
        if not data or offset >= total:
            break
    return rows


def cmd_eia_hourly(year: int, respondent: str) -> Path:
    settings = get_settings()
    key = settings.require_eia_key()
    out_dir = settings.data_raw_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"eia_{respondent.lower()}_fueltype_{year}.csv"
    rows = fetch_year(year, respondent, key)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    m = Manifest(run_name="scripts.download.eia-hourly")
    m.set_param("endpoint", f"{BASE}/data/")
    m.set_param("respondent", respondent)
    m.set_param("year", year)
    m.set_param("rows", len(rows))
    m.register_output(out, kind="eia_hourly_fueltype")
    m.write(out.with_suffix(".manifest.json"))
    print(f"wrote {out.relative_to(REPO_ROOT)} ({len(rows)} rows)")
    return out


def cmd_eia_facets() -> None:
    settings = get_settings()
    key = settings.require_eia_key()
    for facet in ("fueltype", "respondent"):
        doc = _get(f"{BASE}/facet/{facet}", {}, key)
        out = settings.data_raw_dir / f"eia_facet_{facet}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2))
        print(f"wrote {out.relative_to(REPO_ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("eia-hourly", help="EIA v2 hourly generation by fuel type for one year")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--respondent", default="ERCO")
    sub.add_parser("eia-facets", help="save the fueltype and respondent facet lists")
    args = parser.parse_args(argv)
    if args.cmd == "eia-hourly":
        cmd_eia_hourly(args.year, args.respondent)
        return 0
    if args.cmd == "eia-facets":
        cmd_eia_facets()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
