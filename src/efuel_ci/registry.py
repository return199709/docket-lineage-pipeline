"""Factor registry: load, validate and look up cited emission/process factors.

Every factor lives in `factors/*.yaml` and must carry an id, value, unit, low/high range,
a citation (`source`), a `url`, a `vintage` and a `verification` record. Nothing in the
engine may use a number that is not in the registry; nothing in the registry may lack a
citation. `Registry.require_verified` is the gate that strict runs use to refuse factors
whose value has not been checked against its cited source.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from efuel_ci.config import REPO_ROOT

DEFAULT_FACTORS_DIR = REPO_ROOT / "factors"


class VerificationStatus(StrEnum):
    """How the recorded value relates to its cited source.

    primary    - value seen in the primary document's own text this session
    secondary  - value seen quoted by a secondary source that cites the primary document
    derived    - computed from other registry factors or stoichiometry (method says how)
    unverified - from the author's knowledge of the cited source; blocked in strict mode
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    DERIVED = "derived"
    UNVERIFIED = "unverified"


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus
    date: str = Field(min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    method: str = Field(min_length=3)

    @field_validator("date", mode="before")
    @classmethod
    def _date_to_str(cls, v: Any) -> Any:
        # YAML parses unquoted ISO dates into datetime.date
        return v.isoformat() if hasattr(v, "isoformat") else v


class Factor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=3)
    value: float
    unit: str = Field(min_length=1)
    low: float
    high: float
    source: str = Field(min_length=10, description="Citation: document, table, page")
    url: HttpUrl
    vintage: int = Field(ge=1990, le=2100)
    verification: Verification
    notes: str = ""
    category: str = ""

    @model_validator(mode="after")
    def _range_brackets_value(self) -> Factor:
        if not (self.low <= self.value <= self.high):
            raise ValueError(
                f"{self.id}: low <= value <= high violated ({self.low}, {self.value}, {self.high})"
            )
        return self

    @property
    def is_verified(self) -> bool:
        return self.verification.status is not VerificationStatus.UNVERIFIED

    def citation(self) -> str:
        return f"{self.source} ({self.vintage}) <{self.url}>"


class RegistryError(ValueError):
    pass


class Registry:
    """In-memory, read-only view over all factor files."""

    def __init__(self, factors: Iterable[Factor], files: list[Path] | None = None):
        self._factors: dict[str, Factor] = {}
        for f in factors:
            if f.id in self._factors:
                raise RegistryError(f"duplicate factor id: {f.id}")
            self._factors[f.id] = f
        self.files: list[Path] = list(files or [])

    # -- lookups -------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._factors)

    def __iter__(self) -> Iterator[Factor]:
        return iter(self._factors.values())

    def __contains__(self, factor_id: str) -> bool:
        return factor_id in self._factors

    def get(self, factor_id: str) -> Factor:
        try:
            return self._factors[factor_id]
        except KeyError:
            raise RegistryError(f"unknown factor id: {factor_id!r}") from None

    def value(self, factor_id: str, unit: str | None = None) -> float:
        f = self.get(factor_id)
        if unit is not None and f.unit != unit:
            raise RegistryError(f"{factor_id}: expected unit {unit!r}, registry has {f.unit!r}")
        return f.value

    def range(self, factor_id: str) -> tuple[float, float, float]:
        f = self.get(factor_id)
        return f.low, f.value, f.high

    def ids(self) -> list[str]:
        return list(self._factors)

    def by_category(self, category: str) -> list[Factor]:
        return [f for f in self if f.category == category]

    def by_status(self, status: VerificationStatus | str) -> list[Factor]:
        status = VerificationStatus(status)
        return [f for f in self if f.verification.status is status]

    def status_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in VerificationStatus}
        for f in self:
            counts[f.verification.status.value] += 1
        return counts

    def require_verified(self, factor_ids: Iterable[str]) -> None:
        """Raise if any of the given factors is still `unverified`."""
        bad = [fid for fid in factor_ids if not self.get(fid).is_verified]
        if bad:
            raise RegistryError(
                "refusing to use unverified factors (check them against their cited source and "
                f"update `verification` first): {', '.join(bad)}"
            )

    # -- reporting -----------------------------------------------------------
    def rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": f.id,
                "category": f.category,
                "value": f.value,
                "unit": f.unit,
                "low": f.low,
                "high": f.high,
                "vintage": f.vintage,
                "status": f.verification.status.value,
                "source": f.source,
                "url": str(f.url),
            }
            for f in self
        ]

    def list(self, fmt: str = "table") -> str:
        """Render the citation table as text ('table'), 'csv' or 'markdown'."""
        rows = self.rows()
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
            return buf.getvalue()
        cols = ["id", "value", "unit", "low", "high", "vintage", "status", "source"]
        if fmt == "markdown":
            head = "| " + " | ".join(cols) + " |\n|" + "|".join("---" for _ in cols) + "|\n"
            body = "\n".join(
                "| " + " | ".join(str(r[c]).replace("|", "/") for c in cols) + " |" for r in rows
            )
            return head + body + "\n"
        widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
        widths["source"] = min(widths["source"], 70)
        line = "  ".join(c.ljust(widths[c]) for c in cols)
        out = [line, "-" * len(line)]
        for r in rows:
            cells = []
            for c in cols:
                s = str(r[c])
                if c == "source" and len(s) > 70:
                    s = s[:67] + "..."
                cells.append(s.ljust(widths[c]))
            out.append("  ".join(cells))
        counts = self.status_counts()
        out.append("-" * len(line))
        out.append(
            f"{len(self)} factors; verification: "
            + ", ".join(f"{k}={v}" for k, v in counts.items())
        )
        return "\n".join(out) + "\n"


def _load_file(path: Path) -> list[Factor]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "factors" not in doc or "category" not in doc:
        raise RegistryError(f"{path}: expected a mapping with 'category' and 'factors'")
    category = str(doc["category"])
    out: list[Factor] = []
    for raw in doc["factors"]:
        if not isinstance(raw, dict):
            raise RegistryError(f"{path}: factor entries must be mappings")
        try:
            out.append(Factor(**{**raw, "category": category}))
        except Exception as exc:  # re-raise with file + id context
            raise RegistryError(f"{path.name}: {raw.get('id', '<no id>')}: {exc}") from exc
    return out


def load_registry(factors_dir: Path | str = DEFAULT_FACTORS_DIR) -> Registry:
    d = Path(factors_dir)
    files = sorted(d.glob("*.yaml"))
    if not files:
        raise RegistryError(f"no factor files found in {d}")
    factors: list[Factor] = []
    for p in files:
        factors.extend(_load_file(p))
    return Registry(factors, files=files)
