"""Unit conversions and physical identities.

These are the *only* numeric constants allowed outside the factor registry: exact
conversion factors and chemical identities. Anything measured, modelled or legislated
belongs in `factors/*.yaml`.
"""

from __future__ import annotations

MJ_PER_KWH = 3.6
KWH_PER_MJ = 1.0 / MJ_PER_KWH
MJ_PER_GJ = 1_000.0
MJ_PER_TJ = 1_000_000.0
KG_PER_LB = 0.45359237
LB_PER_KG = 1.0 / KG_PER_LB
MJ_PER_MMBTU = 1_055.05585262
KG_PER_SHORT_TON = 907.18474
KM_PER_MILE = 1.609344
G_PER_KG = 1_000.0
KG_PER_TONNE = 1_000.0

# chemistry
M_CO2 = 44.0095  # g/mol
M_C = 12.0107
M_H2 = 2.01588
M_CH2 = 14.02658  # one -CH2- unit of a Fischer-Tropsch paraffin
CO2_PER_C = M_CO2 / M_C  # 44/12


def lb_per_mwh_to_g_per_kwh(x: float) -> float:
    """lb/MWh -> g/kWh (1 lb = 453.59 g; 1 MWh = 1000 kWh)."""
    return x * KG_PER_LB * G_PER_KG / 1_000.0


def lb_per_kwh_to_g_per_kwh(x: float) -> float:
    return x * KG_PER_LB * G_PER_KG


def lb_per_mmbtu_to_g_per_mj(x: float) -> float:
    return x * KG_PER_LB * G_PER_KG / MJ_PER_MMBTU


def kg_per_tj_to_g_per_mj(x: float) -> float:
    """kg/TJ -> g/MJ (1 kg/TJ = 1e3 g / 1e6 MJ)."""
    return x * G_PER_KG / MJ_PER_TJ


def g_per_kwh_to_g_per_mj(x: float) -> float:
    return x * KWH_PER_MJ


def g_per_mj_to_g_per_kwh(x: float) -> float:
    return x * MJ_PER_KWH


def kwh_per_kg_to_mj_per_kg(x: float) -> float:
    return x * MJ_PER_KWH


def ton_mile_to_kg_km(x: float) -> float:
    """kg CO2e per short-ton-mile -> kg CO2e per kg-km."""
    return x / KG_PER_SHORT_TON / KM_PER_MILE
