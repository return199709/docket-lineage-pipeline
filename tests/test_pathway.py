"""M2 tests: stage sums, mass/energy balance, treatment flag, published-figure checks."""

from __future__ import annotations

import pytest

from efuel_ci import units as u
from efuel_ci.pathway import (
    STAGE_ORDER,
    PathwayInputs,
    breakeven_electricity_ci,
    compute,
)


@pytest.fixture
def grid_point_source(registry):
    return compute(
        PathwayInputs(electricity_ci=400.0, co2_source="point_source", transport_miles=500),
        registry,
    )


def test_stage_keys_and_sum(grid_point_source):
    r = grid_point_source
    assert tuple(r.stages) == STAGE_ORDER
    assert r.total == pytest.approx(sum(r.stages.values()))
    assert r.production == pytest.approx(
        r.total - r.stages["combustion"] - r.stages["captured_co2_credit"]
    )
    assert r.stages["ft_synthesis"] == 0.0
    assert r.stages["transport"] > 0


def test_carbon_balance(registry, grid_point_source):
    """CO2 captured per MJ (stoichiometric) must match CO2 released on combustion within 2 %."""
    r = grid_point_source
    captured_g_per_mj = (
        r.mass["co2_kg_per_kg_fuel"] / registry.value("jet_kerosene_ncv") * u.G_PER_KG
    )
    assert captured_g_per_mj == pytest.approx(r.stages["combustion"], rel=0.02)


def test_hydrogen_mass_balance_within_registry_range(registry, grid_point_source):
    """H2 implied by the FT efficiency must sit inside the stoichiometric low/high range."""
    lo, _, hi = registry.range("ft_stoich_h2_per_kg_fuel")
    assert lo <= grid_point_source.mass["h2_kg_per_kg_fuel"] <= hi


def test_electricity_scales_linearly(registry):
    base = PathwayInputs(electricity_ci=0.0, co2_source="dac_solid_sorbent")
    r0 = compute(base, registry)
    r1 = compute(PathwayInputs(**{**base.__dict__, "electricity_ci": 100.0}), registry)
    r2 = compute(PathwayInputs(**{**base.__dict__, "electricity_ci": 200.0}), registry)
    assert r2.total - r1.total == pytest.approx(r1.total - r0.total)
    assert r1.total - r0.total == pytest.approx(100.0 * r1.energy["electricity_kwh"])


def test_zero_carbon_electricity_point_source_is_near_zero(registry):
    r = compute(
        PathwayInputs(
            electricity_ci=0.0,
            co2_source="point_source",
            include_point_source_capture_heat=False,
            transport_mode="none",
        ),
        registry,
    )
    assert r.total == pytest.approx(0.0, abs=1e-9)


def test_treatment_flag(registry):
    neutral = compute(PathwayInputs(electricity_ci=0.0, co2_treatment="neutral"), registry)
    fossil = compute(PathwayInputs(electricity_ci=0.0, co2_treatment="fossil_attributed"), registry)
    comb = u.kg_per_tj_to_g_per_mj(registry.value("jet_kerosene_co2_ef"))
    assert neutral.stages["captured_co2_credit"] == pytest.approx(-comb)
    assert fossil.stages["captured_co2_credit"] == 0.0
    assert fossil.total - neutral.total == pytest.approx(comb)


def test_overall_efficiency_matches_icct_cross_check(registry):
    """Fuel LHV / total energy in should land inside the ICCT 46-51 % band (point source)."""
    r = compute(
        PathwayInputs(
            electricity_ci=0.0, co2_source="point_source", include_point_source_capture_heat=False
        ),
        registry,
    )
    eff = 1.0 / (r.energy["electricity_kwh"] * u.MJ_PER_KWH)
    lo, _, hi = registry.range("ptl_overall_efficiency_point_source")
    assert lo - 0.02 <= eff <= hi + 0.02, eff


def test_factor_ids_recorded(grid_point_source):
    assert "electrolysis_efficiency_lhv" in grid_point_source.factor_ids
    assert "jet_kerosene_co2_ef" in grid_point_source.factor_ids


def test_override_applies(registry):
    base = PathwayInputs(electricity_ci=300.0)
    r = compute(base, registry)
    r_hi = compute(
        PathwayInputs(
            **{**base.__dict__, "factor_overrides": {"electrolysis_efficiency_lhv": 0.75}}
        ),
        registry,
    )
    assert r_hi.stages["electrolysis"] < r.stages["electrolysis"]


# ---- published-figure checks (see docs/methodology.md section 3.4) ----------------


def test_published_concawe_2050_north_europe(registry):
    """Concawe/Aramco e-fuels study (Concawe Review 33(1), 2025): ~5.5 gCO2eq/MJ cradle-to-grave
    for North-Europe e-FT fuels in 2050 (DAC CO2, renewable power, 75 % electrolysis)."""
    target = 5.5
    r = compute(
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
    assert r.total == pytest.approx(target, rel=0.10), r.total


def test_published_liu2020_breakeven(registry):
    """Liu, Sandhu, McCoy, Bergerson (2020) Sustainable Energy & Fuels 4:3129: the DAC + FT
    pathway beats conventional diesel only below 139 gCO2e/kWh electricity."""
    target = 139.0
    comparator = registry.value(
        "rfnbo_fossil_comparator", "gCO2e/MJ"
    )  # assumption, see methodology
    be = breakeven_electricity_ci(
        PathwayInputs(
            electricity_ci=0.0,
            co2_source="dac_liquid_solvent",
            fuel="ediesel",
            transport_mode="none",
        ),
        comparator,
        registry,
    )
    assert be == pytest.approx(target, rel=0.10), be
