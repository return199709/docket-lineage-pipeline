"""Command-line entry points: `efuel-ci factors`, `efuel-ci run`."""

from __future__ import annotations

import argparse
import sys

from efuel_ci import __version__
from efuel_ci.registry import load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="efuel-ci", description="eFuel carbon-intensity engine")
    parser.add_argument("--version", action="version", version=f"efuel-ci {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fac = sub.add_parser("factors", help="print the factor citation table")
    p_fac.add_argument("--format", choices=["table", "csv", "markdown"], default="table")
    p_fac.add_argument("--category", default=None)

    sub.add_parser("run", help="run the pipeline (results/summary.json + lineage.json)")

    args = parser.parse_args(argv)
    if args.cmd == "factors":
        reg = load_registry()
        if args.category:
            from efuel_ci.registry import Registry

            reg = Registry(reg.by_category(args.category), files=reg.files)
        sys.stdout.write(reg.list(args.format))
        return 0
    if args.cmd == "run":
        from efuel_ci.pipeline import run

        run()
        return 0
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
