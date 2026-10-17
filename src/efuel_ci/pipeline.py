"""`make run` entry point: scenarios -> results/summary.json + results/lineage.json.

M1 state: loads and validates the registry, writes a registry summary and the lineage
manifest. Scenario results are added at M5.
"""

from __future__ import annotations

import json
from pathlib import Path

from efuel_ci.config import get_settings
from efuel_ci.lineage import Manifest
from efuel_ci.pathway import PathwayInputs, breakeven_electricity_ci, compute
from efuel_ci.registry import Registry, load_registry


def published_figure_checks(registry: Registry) -> dict:
    """The two reproduction checks from docs/methodology.md section 3.4 (also enforced as tests)."""
    concawe = compute(
        PathwayInputs(
            electricity_ci=registry.value("lca_wind_onshore_ar5", "gCO2e/kWh"),
            co2_source="dac_solid_sorbent",
            capture_heat_source="waste_heat",
            transport_mode="rail",
            transport_miles=300,
            factor_overrides={
                "electrolysis_efficiency_lhv": registry.range("electrolysis_efficiency_lhv")[2]
            },
        ),
        registry,
    )
    liu_inputs = PathwayInputs(
        electricity_ci=0.0, co2_source="dac_liquid_solvent", fuel="ediesel", transport_mode="none"
    )
    comparator = registry.value("rfnbo_fossil_comparator", "gCO2e/MJ")
    be = breakeven_electricity_ci(liu_inputs, comparator, registry)
    return {
        "concawe_2050_north_europe": {
            "published_g_per_mj": 5.5,
            "model_g_per_mj": round(concawe.total, 3),
            "gap_pct": round((concawe.total / 5.5 - 1) * 100, 1),
            "stages": {k: round(v, 3) for k, v in concawe.stages.items()},
            "factor_ids": list(concawe.factor_ids),
        },
        "liu2020_breakeven_electricity_ci": {
            "published_g_per_kwh": 139.0,
            "model_g_per_kwh": round(be, 1),
            "gap_pct": round((be / 139.0 - 1) * 100, 1),
            "comparator_g_per_mj": comparator,
            "comparator_factor_id": "rfnbo_fossil_comparator",
        },
    }


def run(results_dir: Path | None = None) -> dict:
    settings = get_settings()
    results_dir = Path(results_dir or settings.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(run_name="efuel_ci.pipeline.run")
    registry = load_registry(settings.factors_dir)
    for p in registry.files:
        manifest.register_input(p, kind="factor_registry")

    summary = {
        "milestone": "M2",
        "registry": {
            "n_factors": len(registry),
            "verification": registry.status_counts(),
            "unverified_ids": [f.id for f in registry if not f.is_verified],
            "files": [p.name for p in registry.files],
        },
        "published_figure_checks": published_figure_checks(registry),
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
