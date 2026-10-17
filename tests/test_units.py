from __future__ import annotations

import pytest

from efuel_ci import units as u


def test_round_trips():
    assert u.g_per_mj_to_g_per_kwh(u.g_per_kwh_to_g_per_mj(100.0)) == pytest.approx(100.0)
    assert u.lb_per_mwh_to_g_per_kwh(1000.0) == pytest.approx(453.59237)
    assert u.lb_per_kwh_to_g_per_kwh(1.0) == pytest.approx(453.59237)


def test_known_identities():
    # 1 kWh = 3.6 MJ; 1 MMBtu = 1055.06 MJ; 1 kg/TJ = 1e-3 g/MJ
    assert u.kwh_per_kg_to_mj_per_kg(33.3333) == pytest.approx(120.0, rel=1e-4)
    assert u.kg_per_tj_to_g_per_mj(71_500) == pytest.approx(71.5)
    assert u.lb_per_mmbtu_to_g_per_mj(116.65) == pytest.approx(50.15, rel=1e-3)
    assert u.CO2_PER_C == pytest.approx(44.01 / 12.011, rel=1e-4)


def test_eia_and_ipcc_gas_factors_agree(registry):
    """EIA 116.65 lb CO2/MMBtu (HHV) vs IPCC 56,100 kg/TJ (LHV) differ by the HHV/LHV ratio."""
    eia = u.lb_per_mmbtu_to_g_per_mj(registry.value("eia_natural_gas_combustion_co2_per_mmbtu"))
    ipcc = u.kg_per_tj_to_g_per_mj(registry.value("natural_gas_co2_ef"))
    assert ipcc / eia == pytest.approx(registry.value("ng_hhv_to_lhv_ratio"), rel=0.03)


def test_ton_mile_conversion():
    assert u.ton_mile_to_kg_km(1.0) == pytest.approx(1 / 907.18474 / 1.609344)
