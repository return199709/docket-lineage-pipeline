"""Run lineage: every file read or written is registered with a content hash.

`Manifest` is written to `results/lineage.json` at the end of each run so that
every number in the README can be traced to the exact inputs that produced it.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from efuel_ci import __version__
from efuel_ci.config import REPO_ROOT


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001 - lineage must never break a run
        return None


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


@dataclass
class Manifest:
    """Collects inputs, outputs and parameters for one run."""

    run_name: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def register_input(self, path: Path | str, **meta: Any) -> str:
        p = Path(path)
        digest = sha256_file(p)
        self.inputs[_rel(p)] = {"sha256": digest, "bytes": p.stat().st_size, **meta}
        return digest

    def register_output(self, path: Path | str, **meta: Any) -> str:
        p = Path(path)
        digest = sha256_file(p)
        self.outputs[_rel(p)] = {"sha256": digest, "bytes": p.stat().st_size, **meta}
        return digest

    def set_param(self, key: str, value: Any) -> None:
        self.params[key] = value

    def note(self, text: str) -> None:
        self.notes.append(text)

    def run_hash(self) -> str:
        """Deterministic hash over inputs, params and outputs (not timestamps)."""
        payload = json.dumps(
            {"inputs": self.inputs, "params": self.params, "outputs": self.outputs},
            sort_keys=True,
            default=str,
        )
        return sha256_text(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "run_hash": self.run_hash(),
            "started_at": self.started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "efuel_ci_version": __version__,
            "git_commit": _git_commit(),
            "python": platform.python_version(),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "params": self.params,
            "notes": self.notes,
        }

    def write(self, path: Path | str = REPO_ROOT / "results" / "lineage.json") -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False, default=str) + "\n")
        return p
