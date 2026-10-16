from __future__ import annotations

import json
from pathlib import Path

from efuel_ci.lineage import Manifest, sha256_file


def test_manifest_registers_and_hashes(tmp_path: Path):
    src = tmp_path / "in.txt"
    src.write_text("hello")
    out = tmp_path / "out.txt"
    out.write_text("world")
    m = Manifest(run_name="test")
    m.register_input(src, kind="x")
    m.register_output(out)
    m.set_param("alpha", 1)
    h1 = m.run_hash()
    assert len(h1) == 64
    assert next(iter(m.inputs.values()))["sha256"] == sha256_file(src)
    m2 = Manifest(run_name="test")
    m2.register_input(src, kind="x")
    m2.register_output(out)
    m2.set_param("alpha", 1)
    assert m2.run_hash() == h1, "hash must be deterministic and timestamp-free"
    m2.set_param("alpha", 2)
    assert m2.run_hash() != h1


def test_manifest_write(tmp_path: Path):
    m = Manifest(run_name="test")
    p = m.write(tmp_path / "lineage.json")
    doc = json.loads(p.read_text())
    assert doc["run_name"] == "test"
    assert doc["run_hash"] == m.run_hash()
    assert "efuel_ci_version" in doc
