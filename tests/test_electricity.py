"""M3 tests: annual eGRID CI, hourly series validation, matching arithmetic (synthetic fixture)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from efuel_ci import units as u
from efuel_ci.electricity import (
    STORAGE_CODES,
    annual_average_ci_egrid,
    annual_average_ci_from_series,
    clean_share_series,
    clean_share_to_clear,
    flat_load,
    fuel_factor_g_per_kwh,
    hourly_ci,
    hours_in_year,
    load_eia_fueltype_csv,
    match_contracted,
    validate_hourly,
)
from tests.synthetic_mix import synthetic_mix


@pytest.fixture(scope="module")
def mix():
    return synthetic_mix(2024)


@pytest.fixture(scope="module")
def grid(mix, registry):
    return hourly_ci(mix, registry, basis="direct", delivered=True)


def test_hours_in_year():
    assert hours_in_year(2024) == 8784
    assert hours_in_year(2023) == 8760
    assert hours_in_year(2100) == 8760


def test_annual_egrid_ci(registry):
    gen = annual_average_ci_egrid(registry, delivered=False)
    assert gen == pytest.approx(
        u.lb_per_mwh_to_g_per_kwh(registry.value("egrid2023_erct_co2_output_rate"))
    )
    dl = annual_average_ci_egrid(registry)
    assert dl > gen
    assert dl == pytest.approx(gen / (1 - registry.value("egrid2023_erct_grid_gross_loss")))


def test_fuel_factors(registry):
    assert fuel_factor_g_per_kwh(registry, "WND", "direct") == 0.0
    assert fuel_factor_g_per_kwh(registry, "WND", "lifecycle") == registry.value(
        "lca_wind_onshore_ar5"
    )
    assert fuel_factor_g_per_kwh(registry, "NG", "direct") == pytest.approx(
        u.lb_per_kwh_to_g_per_kwh(registry.value("eia_co2_per_kwh_natural_gas"))
    )
    with pytest.raises(KeyError):
        fuel_factor_g_per_kwh(registry, "XYZ", "direct")
    with pytest.raises(ValueError):
        fuel_factor_g_per_kwh(registry, next(iter(STORAGE_CODES)), "direct")


def test_hourly_series_length_and_no_nans(mix, grid):
    validate_hourly(mix, 2024)
    assert len(grid) == hours_in_year(2024)
    assert not grid.isna().any()
    assert (grid > 0).all()
    # CI must lie between the cleanest and dirtiest fuel factors (delivered)
    assert grid.max() < u.lb_per_kwh_to_g_per_kwh(2.31) / (1 - 0.042) + 1e-9


def test_validate_rejects_bad_frames(mix):
    with pytest.raises(ValueError):
        validate_hourly(mix.iloc[:-1], 2024)
    bad = mix.copy()
    bad.iloc[10, 1] = np.nan
    with pytest.raises(ValueError):
        validate_hourly(bad, 2024)


def test_hourly_ci_is_generation_weighted(registry):
    idx = pd.date_range("2024-01-01", periods=2, freq="h", tz="UTC")
    mix = pd.DataFrame({"NG": [100.0, 0.0], "WND": [0.0, 100.0]}, index=idx)
    ci = hourly_ci(mix, registry, delivered=False)
    assert ci.iloc[0] == pytest.approx(fuel_factor_g_per_kwh(registry, "NG", "direct"))
    assert ci.iloc[1] == 0.0


def test_storage_and_negative_values_excluded(registry):
    idx = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    mix = pd.DataFrame({"NG": [100.0], "WND": [-20.0], "BAT": [50.0]}, index=idx)
    ci = hourly_ci(mix, registry, delivered=False)
    assert ci.iloc[0] == pytest.approx(fuel_factor_g_per_kwh(registry, "NG", "direct"))


def test_lifecycle_basis_counts_clean_generation(registry):
    """Lifecycle basis charges wind/solar/nuclear their AR5 medians; direct basis charges zero."""
    idx = pd.date_range("2024-01-01", periods=1, freq="h", tz="UTC")
    mix = pd.DataFrame({"WND": [50.0], "SUN": [50.0]}, index=idx)
    assert hourly_ci(mix, registry, basis="direct", delivered=False).iloc[0] == 0.0
    lc = hourly_ci(mix, registry, basis="lifecycle", delivered=False).iloc[0]
    assert lc == pytest.approx(
        0.5 * registry.value("lca_wind_onshore_ar5")
        + 0.5 * registry.value("lca_solar_pv_utility_ar5")
    )


def test_load_csv_roundtrip(tmp_path, mix):
    long = mix.iloc[:48].stack().reset_index()
    long.columns = ["period", "fueltype", "value"]
    long["period"] = long["period"].dt.strftime("%Y-%m-%dT%H")
    p = tmp_path / "x.csv"
    long.to_csv(p, index=False)
    wide = load_eia_fueltype_csv(p)
    assert wide.shape == (48, mix.shape[1])
    assert np.allclose(wide.to_numpy(), mix.iloc[:48][wide.columns].to_numpy())


# ---- matching ----------------------------------------------------------------------


def test_annual_matching_equals_annual_average_formula(grid):
    load = flat_load(grid.index)
    annual = annual_average_ci_from_series(grid, load)
    for s in (0.0, 0.5, 0.8, 1.0):
        r = match_contracted(load, grid, clean_share=s, window="year")
        assert r.ci_g_per_kwh == pytest.approx((1 - s) * annual)
        assert r.matched_fraction == pytest.approx(s)
        assert r.surplus_fraction == pytest.approx(0.0, abs=1e-12)


def test_flat_profile_makes_windows_equivalent(grid):
    """With a flat clean profile and flat load, hourly == monthly == annual matching."""
    load = flat_load(grid.index)
    y = match_contracted(load, grid, clean_share=0.6, window="year").ci_g_per_kwh
    m = match_contracted(load, grid, clean_share=0.6, window="month").ci_g_per_kwh
    h = match_contracted(load, grid, clean_share=0.6, window="hour").ci_g_per_kwh
    assert y == pytest.approx(m) == pytest.approx(h)


def test_shaped_profile_hourly_is_worse_than_annual(mix, grid):
    """Solar-shaped contracted power leaves residual hours under hourly matching."""
    load = flat_load(grid.index)
    prof = mix["SUN"]
    ry = match_contracted(load, grid, clean_share=0.8, window="year", clean_profile=prof)
    rm = match_contracted(load, grid, clean_share=0.8, window="month", clean_profile=prof)
    rh = match_contracted(load, grid, clean_share=0.8, window="hour", clean_profile=prof)
    assert ry.ci_g_per_kwh <= rm.ci_g_per_kwh <= rh.ci_g_per_kwh
    assert rh.surplus_fraction > 0
    assert rh.matched_fraction + rh.residual_fraction == pytest.approx(1.0)
    assert rh.hourly_ci.min() >= 0


def test_over_contracting_hourly_reaches_zero(grid):
    load = flat_load(grid.index)
    r = match_contracted(load, grid, clean_share=1.0, window="hour")
    assert r.ci_g_per_kwh == pytest.approx(0.0, abs=1e-9)
    r2 = match_contracted(load, grid, clean_share=1.5, window="hour")
    assert r2.surplus_fraction == pytest.approx(0.5)


def test_clean_ci_applies_to_matched_energy(grid):
    load = flat_load(grid.index)
    r = match_contracted(load, grid, clean_share=1.0, window="year", clean_ci=11.0)
    assert r.ci_g_per_kwh == pytest.approx(11.0)


def test_clean_share_to_clear(grid, mix):
    load = flat_load(grid.index)
    target = 60.0
    s = clean_share_to_clear(load, grid, window="year", target_ci_g_per_kwh=target)
    assert match_contracted(load, grid, clean_share=s, window="year").ci_g_per_kwh <= target
    assert match_contracted(load, grid, clean_share=s - 0.01, window="year").ci_g_per_kwh > target
    sh = clean_share_to_clear(
        load, grid, window="hour", target_ci_g_per_kwh=target, clean_profile=mix["WND"]
    )
    assert sh >= s


def test_clean_share_series(mix):
    cs = clean_share_series(mix)
    assert ((cs >= 0) & (cs <= 1)).all()
