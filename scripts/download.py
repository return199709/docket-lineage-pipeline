"""Download raw inputs into data/raw (gitignored). Registers every file in the lineage.

Usage: uv run python scripts/download.py eia-hourly --year 2024
Requires EIA_API_KEY in .env for the EIA endpoints. (Implemented at M3.)
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("eia-hourly", help="EIA v2 hourly generation by fuel type (ERCO)")
    p.add_argument("--year", type=int, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "eia-hourly":
        print("EIA hourly download is implemented at milestone M3.", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
