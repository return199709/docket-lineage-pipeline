from __future__ import annotations

import json
from pathlib import Path

from efuel_ci.cli import main
from efuel_ci.pipeline import run


def test_pipeline_writes_summary_and_lineage(tmp_path: Path):
    summary = run(results_dir=tmp_path)
    assert summary["registry"]["n_factors"] >= 25
    lineage = json.loads((tmp_path / "lineage.json").read_text())
    assert any(k.startswith("factors/") for k in lineage["inputs"])
    assert "results/summary.json" in " ".join(lineage["outputs"]) or any(
        k.endswith("summary.json") for k in lineage["outputs"]
    )


def test_cli_factors(capsys):
    assert main(["factors", "--format", "markdown"]) == 0
    out = capsys.readouterr().out
    assert "corsia_baseline_jet" in out
