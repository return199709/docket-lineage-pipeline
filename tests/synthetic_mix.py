"""SYNTHETIC hourly fuel mix for unit tests only.

This is NOT data. It is a deterministic shape generator (diurnal solar, pseudo-random wind,
gas filling the remainder) used to exercise the matching arithmetic. It never feeds results.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from efuel_ci.electricity import hours_in_year


def synthetic_mix(year: int = 2024, seed: int = 0) -> pd.DataFrame:
    n = hours_in_year(year)
    idx = pd.date_range(f"{year}-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    hour = idx.hour.to_numpy()
    doy = idx.dayofyear.to_numpy()
    demand = (
        45_000
        + 15_000 * np.sin((hour - 6) / 24 * 2 * np.pi) ** 2
        + 8_000 * np.sin((doy - 20) / 366 * 2 * np.pi)
    )
    solar = (
        np.clip(
            np.sin((hour - 13) / 24 * 2 * np.pi) * 0 + np.cos((hour - 13) / 12 * np.pi), 0, None
        )
        * 12_000
    )
    solar *= 0.8 + 0.4 * np.sin((doy - 172) / 366 * 2 * np.pi) ** 2
    wind = np.clip(
        9_000 + 7_000 * rng.standard_normal(n).cumsum() / np.sqrt(np.arange(1, n + 1)) * 0.5,
        1_000,
        25_000,
    )
    nuclear = np.full(n, 4_800.0)
    coal = np.full(n, 7_000.0)
    hydro = np.full(n, 100.0)
    gas = np.clip(demand - solar - wind - nuclear - coal - hydro, 2_000, None)
    return pd.DataFrame(
        {
            "COL": coal,
            "NG": gas,
            "NUC": nuclear,
            "SUN": solar,
            "WAT": hydro,
            "WND": wind,
            "OTH": 150.0,
        },
        index=idx,
    )
