"""`make run` entry point: scenarios -> results/summary.json + results/lineage.json.

M1 state: loads and validates the registry, writes a registry summary and the lineage
manifest. Scenario results are added at M5.
"""

from __future__ import annotations

import json
from pathlib import Path

from efuel_ci.config import get_settings
from efuel_ci.lineage import Manifest
from efuel_ci.registry import load_registry


def run(results_dir: Path | None = None) -> dict:
    settings = get_settings()
    results_dir = Path(results_dir or settings.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(run_name="efuel_ci.pipeline.run")
    registry = load_registry(settings.factors_dir)
    for p in registry.files:
        manifest.register_input(p, kind="factor_registry")

    summary = {
        "milestone": "M1",
        "registry": {
            "n_factors": len(registry),
            "verification": registry.status_counts(),
            "unverified_ids": [f.id for f in registry if not f.is_verified],
            "files": [p.name for p in registry.files],
        },
        "scenarios": None,
        "note": "Scenario carbon intensities are produced from M5 onward.",
    }
    manifest.set_param("factors_dir", str(settings.factors_dir))
    manifest.set_param("n_factors", len(registry))

    summary_path = results_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    manifest.register_output(summary_path, kind="summary")

    table_path = results_dir / "factors.csv"
    table_path.write_text(registry.list("csv"))
    manifest.register_output(table_path, kind="citation_table")

    lineage_path = manifest.write(results_dir / "lineage.json")
    print(f"wrote {summary_path} and {lineage_path} (run_hash={manifest.run_hash()[:12]})")
    return summary


if __name__ == "__main__":
    run()
