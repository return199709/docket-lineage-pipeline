"""Stage model for 1 MJ of power-to-liquid fuel (eSAF by default, eDiesel optional).

Stages (all per MJ of fuel delivered to the aircraft/vehicle):

    electrolysis        H2 production electricity x electricity CI
    co2_capture         DAC (solid-sorbent or liquid-solvent) or point-source capture energy
    ft_synthesis        RWGS + Fischer-Tropsch + upgrading (energy need met by H2; see methodology)
    transport           product distribution by rail/truck/ship
    combustion          gross CO2 from burning the fuel
    captured_co2_credit negative of combustion CO2 when the carbon is captured and counted neutral

The `co2_treatment` flag decides whether combustion carbon of captured origin is netted out
(`neutral`: DAC, biogenic, or point-source CO2 under a rulebook that credits it) or counted
(`fossil_attributed`: fossil point-source CO2 with no credit). Rulebooks (M4) apply their own
treatment on top of these raw stages; this module is rulebook-agnostic.

All numbers come from the registry; the only constants here are unit conversions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from efuel_ci import units as u
from efuel_ci.registry import Registry, load_registry

CO2Source = Literal["dac_solid_sorbent", "dac_liquid_solvent", "point_source"]
CO2Treatment = Literal["neutral", "fossil_attributed"]
HeatSource = Literal["electric", "waste_heat", "natural_gas"]
TransportMode = Literal["rail", "truck", "ship", "none"]
Fuel = Literal["esaf", "ediesel"]

STAGE_ORDER = (
    "electrolysis",
    "co2_capture",
    "ft_synthesis",
    "transport",
    "combustion",
    "captured_co2_credit",
)

_TRANSPORT_FACTOR = {
    "rail": "epa_hub_2025_rail_freight",
    "truck": "epa_hub_2025_truck_freight",
    "ship": "epa_hub_2025_waterborne_freight",
}


@dataclass(frozen=True)
class PathwayInputs:
    """Scenario-level inputs. Factor overrides let the tornado (M5) perturb one factor at a time."""

    electricity_ci: float  # gCO2e/kWh delivered to the plant, for all plant electricity
    co2_source: CO2Source = "point_source"
    co2_treatment: CO2Treatment = "neutral"
    capture_heat_source: HeatSource = "electric"
    fuel: Fuel = "esaf"
    transport_mode: TransportMode = "rail"
    transport_miles: float = 0.0
    include_point_source_capture_heat: bool = True
    factor_overrides: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PathwayResult:
    stages: dict[str, float]  # gCO2e per MJ fuel
    energy: dict[str, float]  # per MJ fuel: kWh electricity, MJ H2, MJ gas, kWh_th heat
    mass: dict[str, float]  # per kg fuel: kg H2, kg CO2
    inputs: PathwayInputs
    factor_ids: tuple[str, ...]

    @property
    def total(self) -> float:
        return sum(self.stages.values())

    @property
    def production(self) -> float:
        """Well-to-tank: everything except combustion and its credit."""
        return sum(
            v for k, v in self.stages.items() if k not in ("combustion", "captured_co2_credit")
        )


class _F:
    """Factor accessor that records every id used and applies overrides."""

    def __init__(self, reg: Registry, overrides: dict[str, float]):
        self.reg, self.overrides, self.used = reg, overrides, []

    def __call__(self, fid: str, unit: str | None = None) -> float:
        self.used.append(fid)
        if fid in self.overrides:
            self.reg.get(fid)  # still validate the id exists
            return self.overrides[fid]
        return self.reg.value(fid, unit=unit)


def fuel_lhv_mj_per_kg(f: _F, fuel: Fuel) -> float:
    return f("jet_kerosene_ncv", "MJ/kg") if fuel == "esaf" else f("gas_diesel_oil_ncv", "MJ/kg")


def combustion_co2_g_per_mj(f: _F, fuel: Fuel) -> float:
    fid = "jet_kerosene_co2_ef" if fuel == "esaf" else "gas_diesel_oil_co2_ef"
    return u.kg_per_tj_to_g_per_mj(f(fid, "kgCO2/TJ"))


def natural_gas_ci_g_per_mj_lhv(f: _F, *, with_combustion: bool) -> float:
    """Supply-chain (+ optional combustion) GHG of natural gas per MJ LHV burned."""
    upstream = f("natural_gas_upstream_ci", "gCO2e/MJ_HHV") * f("ng_hhv_to_lhv_ratio", "ratio")
    if not with_combustion:
        return upstream
    return upstream + u.kg_per_tj_to_g_per_mj(f("natural_gas_co2_ef", "kgCO2/TJ"))


def compute(inputs: PathwayInputs, registry: Registry | None = None) -> PathwayResult:
    reg = registry or load_registry()
    f = _F(reg, inputs.factor_overrides)
    ci = inputs.electricity_ci  # gCO2e/kWh

    lhv = fuel_lhv_mj_per_kg(f, inputs.fuel)  # MJ/kg fuel
    energy: dict[str, float] = {
        "electricity_kwh": 0.0,
        "h2_mj": 0.0,
        "gas_mj": 0.0,
        "heat_kwh_th": 0.0,
    }
    stages: dict[str, float] = dict.fromkeys(STAGE_ORDER, 0.0)

    # --- electrolysis: H2 needed per MJ fuel, electricity per MJ H2 ---------------------
    h2_mj = 1.0 / f("ft_synthesis_efficiency", "fraction")
    el_h2_kwh = h2_mj * u.KWH_PER_MJ / f("electrolysis_efficiency_lhv", "fraction")
    energy["h2_mj"] += h2_mj
    energy["electricity_kwh"] += el_h2_kwh
    stages["electrolysis"] = el_h2_kwh * ci

    # --- CO2 demand: stoichiometric, carbon fully retained at plant boundary ---------
    co2_kg_per_kg_fuel = f("ft_stoich_co2_per_kg_fuel", "kgCO2/kgfuel")
    co2_t_per_mj = co2_kg_per_kg_fuel / lhv / u.KG_PER_TONNE

    # --- CO2 capture energy ---------------------------------------------------------
    cap_el_kwh = 0.0
    cap_heat_kwh_th = 0.0
    cap_gas_mj = 0.0
    gas_co2_captured_in_process = False
    if inputs.co2_source == "dac_solid_sorbent":
        cap_el_kwh = f("dac_solid_sorbent_electricity", "kWh/tCO2") * co2_t_per_mj
        cap_heat_kwh_th = f("dac_solid_sorbent_heat", "kWh_th/tCO2") * co2_t_per_mj
    elif inputs.co2_source == "dac_liquid_solvent":
        cap_el_kwh = f("dac_liquid_solvent_electricity", "kWh/tCO2") * co2_t_per_mj
        cap_gas_mj = f("dac_liquid_solvent_gas", "GJ/tCO2") * u.MJ_PER_GJ * co2_t_per_mj
        gas_co2_captured_in_process = True  # Keith et al. oxy-fired calciner captures its own CO2
    elif inputs.co2_source == "point_source":
        cap_el_kwh = f("co2_compression_electricity", "kWh/tCO2") * co2_t_per_mj
        if inputs.include_point_source_capture_heat:
            cap_heat_kwh_th = (
                f("co2_point_source_capture_heat", "GJ/tCO2")
                * u.MJ_PER_GJ
                * u.KWH_PER_MJ
                * co2_t_per_mj
            )
    else:  # pragma: no cover
        raise ValueError(inputs.co2_source)

    capture_g = cap_el_kwh * ci
    if cap_heat_kwh_th > 0:
        if inputs.capture_heat_source == "electric":
            cap_el_kwh += cap_heat_kwh_th
            capture_g += cap_heat_kwh_th * ci
        elif inputs.capture_heat_source == "natural_gas":
            gas_mj = cap_heat_kwh_th * u.MJ_PER_KWH / f("gas_boiler_efficiency", "fraction")
            cap_gas_mj += gas_mj
            capture_g += gas_mj * natural_gas_ci_g_per_mj_lhv(f, with_combustion=True)
        elif inputs.capture_heat_source == "waste_heat":
            pass  # supplied by FT exotherm; see methodology
        else:  # pragma: no cover
            raise ValueError(inputs.capture_heat_source)
    if gas_co2_captured_in_process and cap_gas_mj > 0:
        capture_g += cap_gas_mj * natural_gas_ci_g_per_mj_lhv(f, with_combustion=False)

    energy["electricity_kwh"] += cap_el_kwh
    energy["heat_kwh_th"] += cap_heat_kwh_th
    energy["gas_mj"] += cap_gas_mj
    stages["co2_capture"] = capture_g

    # --- synthesis/upgrading: no separate emissions (energy folded into FT efficiency) ----
    stages["ft_synthesis"] = 0.0

    # --- transport --------------------------------------------------------------------
    if inputs.transport_mode != "none" and inputs.transport_miles > 0:
        kg_per_ton_mile = f(_TRANSPORT_FACTOR[inputs.transport_mode], "kgCO2e/ton-mile")
        tons_per_mj = 1.0 / lhv / u.KG_PER_SHORT_TON
        stages["transport"] = kg_per_ton_mile * tons_per_mj * inputs.transport_miles * u.G_PER_KG

    # --- combustion and captured-carbon credit ------------------------------------------
    comb = combustion_co2_g_per_mj(f, inputs.fuel)
    stages["combustion"] = comb
    stages["captured_co2_credit"] = -comb if inputs.co2_treatment == "neutral" else 0.0

    mass = {
        "h2_kg_per_kg_fuel": h2_mj * lhv / f("h2_lhv", "MJ/kg"),
        "co2_kg_per_kg_fuel": co2_kg_per_kg_fuel,
    }
    return PathwayResult(
        stages=stages,
        energy=energy,
        mass=mass,
        inputs=inputs,
        factor_ids=tuple(dict.fromkeys(f.used)),
    )


def breakeven_electricity_ci(
    inputs: PathwayInputs, comparator_g_per_mj: float, registry: Registry | None = None
) -> float:
    """Electricity CI (gCO2e/kWh) at which the pathway total equals the comparator.

    The model is affine in electricity CI, so two evaluations suffice.
    """
    reg = registry or load_registry()
    r0 = compute(PathwayInputs(**{**inputs.__dict__, "electricity_ci": 0.0}), reg)
    r1 = compute(PathwayInputs(**{**inputs.__dict__, "electricity_ci": 1.0}), reg)
    slope = r1.total - r0.total  # g/MJ per (g/kWh)
    if slope <= 0:
        raise ValueError("pathway does not depend on electricity CI")
    return (comparator_g_per_mj - r0.total) / slope
