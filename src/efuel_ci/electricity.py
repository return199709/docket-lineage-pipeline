"""Electricity carbon intensity: annual average, hourly series, contracted clean power + matching.

(a) `annual_average_ci_egrid`      ERCOT annual CI from eGRID (generation -> delivered via loss)
(b) `hourly_ci`                    hourly CI from the EIA-930 fuel mix x per-fuel factors
(c) `match_contracted`             contracted clean power with annual / monthly / hourly matching;
                                   residual load is charged at the hourly grid CI of the window

Units: generation in MWh per hour (EIA), CI in gCO2e/kWh. Factor ids are taken from the registry;
the per-fuel mapping below is the only place EIA fuel codes are interpreted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from efuel_ci import units as u
from efuel_ci.registry import Registry, load_registry

Basis = Literal["direct", "lifecycle"]
Window = Literal["year", "month", "hour"]

# EIA-930 fuel-type codes seen in the fuel-type-data route (confirmed: SUN, WAT, NG, OTH, NUC, WND).
# "direct": combustion-only factor id (eGRID-comparable); "lifecycle": IPCC AR5 Annex III median id.
# None means zero for that basis. Codes not listed here raise, so new codes (e.g. storage) must be
# classified deliberately in `STORAGE_CODES` or here before a series can be built.
FUEL_FACTORS: dict[str, dict[Basis, str | None]] = {
    "COL": {"direct": "eia_co2_per_kwh_coal", "lifecycle": "lca_coal_ar5"},
    "NG": {"direct": "eia_co2_per_kwh_natural_gas", "lifecycle": "lca_gas_combined_cycle_ar5"},
    "OIL": {"direct": "eia_co2_per_kwh_petroleum", "lifecycle": "lca_coal_ar5"},
    "OTH": {"direct": "eia_co2_per_kwh_natural_gas", "lifecycle": "lca_gas_combined_cycle_ar5"},
    "NUC": {"direct": None, "lifecycle": "lca_nuclear_ar5"},
    "SUN": {"direct": None, "lifecycle": "lca_solar_pv_utility_ar5"},
    "WAT": {"direct": None, "lifecycle": "lca_hydro_ar5"},
    "WND": {"direct": None, "lifecycle": "lca_wind_onshore_ar5"},
}
# Storage codes (battery, pumped storage, unknown storage) are net consumers over a year; they are
# excluded from both numerator and denominator (their discharge is given the hour's mix CI).
STORAGE_CODES = frozenset({"BAT", "PS", "UES"})
CLEAN_CODES = frozenset({"NUC", "SUN", "WAT", "WND"})


def hours_in_year(year: int) -> int:
    return (
        int(pd.Timestamp(year=year + 1, month=1, day=1).dayofyear and (366 if _leap(year) else 365))
        * 24
    )


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def fuel_factor_g_per_kwh(registry: Registry, code: str, basis: Basis) -> float:
    if code in STORAGE_CODES:
        raise ValueError(f"storage code {code} has no emission factor; exclude it from the mix")
    try:
        fid = FUEL_FACTORS[code][basis]
    except KeyError:
        raise KeyError(
            f"unknown EIA fuel code {code!r}; add it to FUEL_FACTORS or STORAGE_CODES"
        ) from None
    if fid is None:
        return 0.0
    f = registry.get(fid)
    if f.unit == "lbCO2/kWh":
        return u.lb_per_kwh_to_g_per_kwh(f.value)
    if f.unit == "gCO2e/kWh":
        return f.value
    raise ValueError(f"{fid}: unexpected unit {f.unit}")


# --------------------------------------------------------------------------- (a) annual


def annual_average_ci_egrid(
    registry: Registry, *, delivered: bool = True, co2e: bool = False
) -> float:
    """ERCOT annual average CI in gCO2(e)/kWh from eGRID; delivered applies grid gross loss."""
    fid = "egrid2023_erct_co2e_output_rate" if co2e else "egrid2023_erct_co2_output_rate"
    ci = u.lb_per_mwh_to_g_per_kwh(registry.value(fid))
    if delivered:
        ci /= 1.0 - registry.value("egrid2023_erct_grid_gross_loss", "fraction")
    return ci


def to_delivered(ci: pd.Series | float, registry: Registry) -> pd.Series | float:
    return ci / (1.0 - registry.value("egrid2023_erct_grid_gross_loss", "fraction"))


# --------------------------------------------------------------------------- (b) hourly


def load_eia_fueltype_csv(path: Path | str) -> pd.DataFrame:
    """Read the long CSV written by scripts/download.py into a wide hourly frame (MWh by code)."""
    df = pd.read_csv(path)
    required = {"period", "fueltype", "value"}
    if not required <= set(df.columns):
        raise ValueError(f"{path}: expected columns {sorted(required)}, got {list(df.columns)}")
    df["period"] = pd.to_datetime(df["period"], utc=True)
    wide = df.pivot_table(index="period", columns="fueltype", values="value", aggfunc="sum")
    wide = wide.sort_index()
    wide.columns.name = None
    return wide


def validate_hourly(mix: pd.DataFrame, year: int) -> None:
    """Raise unless the frame covers every hour of `year` exactly once with no NaNs."""
    n = hours_in_year(year)
    if len(mix) != n:
        raise ValueError(f"expected {n} hours for {year}, got {len(mix)}")
    expected = pd.date_range(f"{year}-01-01", periods=n, freq="h", tz="UTC")
    if not mix.index.equals(expected):
        raise ValueError("index is not a complete, ordered UTC hourly range for the year")
    if mix.isna().any().any():
        raise ValueError("fuel mix contains NaNs")


def hourly_ci(
    mix: pd.DataFrame, registry: Registry, *, basis: Basis = "direct", delivered: bool = True
) -> pd.Series:
    """Generation-weighted CI per hour (gCO2e/kWh) from a wide MWh-by-code frame."""
    gen_cols = [c for c in mix.columns if c not in STORAGE_CODES]
    factors = {c: fuel_factor_g_per_kwh(registry, c, basis) for c in gen_cols}
    gen = mix[gen_cols].clip(lower=0.0)  # negative = net consumption; no generation to attribute
    total = gen.sum(axis=1)
    if (total <= 0).any():
        raise ValueError("hour with zero total generation")
    emissions = sum(gen[c] * factors[c] for c in gen_cols)  # MWh * g/kWh == kg
    ci = emissions / total
    ci.name = f"ci_{basis}_g_per_kwh"
    if delivered:
        ci = to_delivered(ci, registry)
    return ci


def annual_average_ci_from_series(ci: pd.Series, weights: pd.Series | None = None) -> float:
    if weights is None:
        return float(ci.mean())
    return float((ci * weights).sum() / weights.sum())


def clean_share_series(mix: pd.DataFrame) -> pd.Series:
    gen_cols = [c for c in mix.columns if c not in STORAGE_CODES]
    gen = mix[gen_cols].clip(lower=0.0)
    clean = gen[[c for c in gen_cols if c in CLEAN_CODES]].sum(axis=1)
    return clean / gen.sum(axis=1)


# --------------------------------------------------------------------------- (c) matching


@dataclass(frozen=True)
class MatchResult:
    window: Window
    clean_share: float  # contracted clean energy / annual load
    ci_g_per_kwh: float  # load-weighted delivered CI of the plant's electricity
    matched_fraction: float  # share of annual load covered by contracted clean within windows
    residual_fraction: float
    surplus_fraction: float  # contracted clean not usable within its window / annual load
    hourly_ci: pd.Series  # per-hour CI actually charged to the plant


def _window_key(index: pd.DatetimeIndex, window: Window) -> pd.Series | np.ndarray:
    if window == "year":
        return np.zeros(len(index), dtype=int)
    if window == "month":
        return index.month.to_numpy()
    if window == "hour":
        return np.arange(len(index))
    raise ValueError(window)


def match_contracted(
    load: pd.Series,
    grid_ci: pd.Series,
    *,
    clean_share: float,
    window: Window,
    clean_profile: pd.Series | None = None,
    clean_ci: float = 0.0,
) -> MatchResult:
    """Charge the plant's load with contracted clean power matched inside `window`.

    load          hourly plant load (MWh), index == grid_ci index
    grid_ci       hourly delivered grid CI (gCO2e/kWh) used for the residual
    clean_share   contracted clean energy as a fraction of annual load (may exceed 1)
    clean_profile hourly shape of the contracted supply (any scale; None = flat); scaled so
                  that its annual sum equals clean_share x annual load
    clean_ci      CI assigned to matched clean energy (0 for 'direct'; a lifecycle value otherwise)

    Within each window, matched = min(load, clean); residual = load - matched at the window's
    load-weighted grid CI; surplus clean is not banked across windows.
    """
    if not load.index.equals(grid_ci.index):
        raise ValueError("load and grid_ci must share the same hourly index")
    if clean_share < 0:
        raise ValueError("clean_share must be >= 0")
    annual_load = float(load.sum())
    if clean_profile is None:
        clean = pd.Series(
            np.full(len(load), clean_share * annual_load / len(load)), index=load.index
        )
    else:
        if not clean_profile.index.equals(load.index):
            raise ValueError("clean_profile must share the load index")
        prof = clean_profile.clip(lower=0.0)
        if prof.sum() <= 0:
            raise ValueError("clean_profile has no energy")
        clean = prof * (clean_share * annual_load / float(prof.sum()))

    keys = _window_key(load.index, window)
    df = pd.DataFrame(
        {"load": load.to_numpy(), "clean": clean.to_numpy(), "ci": grid_ci.to_numpy()}
    )
    df["key"] = keys
    g = df.groupby("key")
    win_load = g["load"].transform("sum")
    win_clean = g["clean"].transform("sum")
    win_matched = np.minimum(win_load, win_clean)
    # residual energy in the window is spread over its hours in proportion to load
    frac_residual = np.where(win_load > 0, 1.0 - win_matched / win_load, 0.0)
    residual_h = df["load"] * frac_residual
    matched_h = df["load"] - residual_h
    charged_h = residual_h * df["ci"] + matched_h * clean_ci  # MWh * g/kWh = kg
    hourly = pd.Series(
        np.where(df["load"] > 0, charged_h / df["load"].replace(0, np.nan), 0.0), index=load.index
    ).fillna(0.0)
    hourly.name = f"ci_matched_{window}_g_per_kwh"
    matched_total = float(matched_h.sum())
    surplus_total = float((df["clean"] - matched_h).clip(lower=0).sum())
    return MatchResult(
        window=window,
        clean_share=clean_share,
        ci_g_per_kwh=float(charged_h.sum() / annual_load),
        matched_fraction=matched_total / annual_load,
        residual_fraction=1.0 - matched_total / annual_load,
        surplus_fraction=surplus_total / annual_load,
        hourly_ci=hourly,
    )


def flat_load(index: pd.DatetimeIndex, mw: float = 1.0) -> pd.Series:
    return pd.Series(np.full(len(index), float(mw)), index=index, name="load_mwh")


def clean_share_to_clear(
    load: pd.Series,
    grid_ci: pd.Series,
    *,
    window: Window,
    target_ci_g_per_kwh: float,
    clean_profile: pd.Series | None = None,
    clean_ci: float = 0.0,
    tol: float = 1e-4,
) -> float:
    """Smallest contracted clean share whose matched CI <= target (bisection; monotone in share)."""
    lo, hi = 0.0, 1.0
    if (
        match_contracted(
            load,
            grid_ci,
            clean_share=hi,
            window=window,
            clean_profile=clean_profile,
            clean_ci=clean_ci,
        ).ci_g_per_kwh
        > target_ci_g_per_kwh
    ):
        hi = 3.0
        if (
            match_contracted(
                load,
                grid_ci,
                clean_share=hi,
                window=window,
                clean_profile=clean_profile,
                clean_ci=clean_ci,
            ).ci_g_per_kwh
            > target_ci_g_per_kwh
        ):
            return float("nan")
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        r = match_contracted(
            load,
            grid_ci,
            clean_share=mid,
            window=window,
            clean_profile=clean_profile,
            clean_ci=clean_ci,
        )
        if r.ci_g_per_kwh <= target_ci_g_per_kwh:
            hi = mid
        else:
            lo = mid
    return hi


def default_registry() -> Registry:  # small helper for scripts
    return load_registry()
