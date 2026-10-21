# Methodology and assumptions

This file is the running log of every simplification and assumption in the engine. Each entry is
added the moment it is made, tagged with the milestone that introduced it. Rulebook-specific
simplifications get their own sections (M4).

## 0. Registry rules (M1)

1. **Every number used by the engine lives in `factors/*.yaml`.** Code never carries a numeric
   emission, energy or threshold constant; it looks it up by factor id. The only numbers allowed in
   code are unit conversions and physical identities (44/12, 3.6 MJ/kWh, 1.05506 GJ/MMBtu, 0.4536 kg/lb).
2. **Every factor carries:** `id`, `name`, `value`, `unit`, `low`, `high`, `source` (document, table,
   page), `url`, `vintage` (year of the data or document), `verification`, optional `notes`.
   The loader (`efuel_ci.registry`) rejects a factor missing any required field, with an empty
   unit or citation, with a non-URL `url`, with unknown fields, or with `value` outside `[low, high]`.
3. **Ranges, not points.** `low`/`high` are the uncertainty or vintage range used by the tornado
   (M5). Where a source gives a confidence interval it is used; where it gives only a point, the
   range is stated as an assumption in the factor's `verification.method` and listed below.
   Physical constants and legal constants have `low == high`.
4. **Verification status** records how the value relates to its cited source, because the primary
   documents could not all be opened from the build environment at M1 (see section 1):
   - `primary` - the value was seen in the primary document's own text this session.
   - `secondary` - the value was seen quoted by a secondary source that cites the primary document.
   - `derived` - computed from other registry factors or stoichiometry; `method` gives the formula.
   - `unverified` - from the author's knowledge of the cited source; **blocked** by
     `Registry.require_verified` and therefore cannot enter a strict run until checked.
   The status is never silently upgraded: changing it requires editing the YAML with the date and
   method of the check.
5. **Vintage policy.** Grid factors use the latest released eGRID edition (eGRID2023, released
   January 2025); the hourly EIA series (M3) will use calendar year 2024 unless the user chooses
   otherwise. A mismatch of one year between eGRID vintage and EIA year is accepted and noted.
6. **Rulebook constants are factors too** (comparators, thresholds, dates), so a rulebook change
   is a YAML diff with a citation, not a code change.
7. **Lineage.** `efuel_ci.lineage.Manifest` records the SHA-256 of every factor file read and every
   result written; `results/lineage.json` carries a deterministic `run_hash` over inputs,
   parameters and outputs (timestamps excluded) so a README number can be matched to a run.

## 1. Environment limitation at M1 (reported, not worked around)

The build environment's network policy blocks direct access to epa.gov, eia.gov, eur-lex.europa.eu,
icao.int, theicct.org, concawe.eu, ipcc.ch, ipcc-nggip.iges.or.jp, arb.ca.gov and greet.anl.gov
(the proxy returns 403 on CONNECT, and the page-fetch tool cannot resolve the hosts). Only web
search snippets were available. Consequences:

- 20 factors are `primary` (the snippet came from the primary host, e.g. eia.gov, icao.int,
  ipcc-nggip.iges.or.jp, energy.gov, concawe.eu, theicct.org).
- 30 are `secondary` (snippet from a mirror or a secondary source quoting the primary document:
  eGRID2023 ERCOT rates, EU comparator 94 gCO2e/MJ and 70 %, EU temporal-correlation dates,
  AR5 Annex III lifecycle medians, EPA Hub 2025 freight factors, AR6 CH4 GWPs).
- 5 are `unverified` and blocked: `gwp100_ch4_ar5`, `gwp100_n2o_ar5`, `gas_diesel_oil_co2_ef`,
  `co2_point_source_capture_heat`, `co2_compression_electricity`.
- The EIA API itself (needed at M3) is also blocked; `EIA_API_KEY` is not set in this environment.

Nothing was substituted with a guessed number: unverified values are flagged, not hidden, and the
verification gate refuses them.

## 2. Assumptions made at M1 (ranges and conventions)

M2 additions to the registry: `dac_solid_sorbent_*` now carry the Climeworks figures (Beuttler et al. 2019, as used by Concawe/LBST); `natural_gas_upstream_ci` (Balcombe et al. 2016, per MJ HHV); `ng_hhv_to_lhv_ratio` and `gas_boiler_efficiency` are unverified assumptions and blocked in strict mode.

| id | assumption |
|---|---|
| `egrid2023_erct_co2_output_rate` | range = eGRID2024 (700.7) to EPA equivalencies-page ERCT value (771.1); a vintage spread, not a statistical interval. |
| `egrid2023_us_co2_output_rate` | the 771.5 lb/MWh value is read from an unlabeled row of the EPA rev. 1 PDF next to a "U.S." marker; provisional. |
| `egrid2023_erct_grid_gross_loss` | 4.2 % read from the ERCT row of the EPA rev. 1 PDF without a visible header; range 4.0-5.5 % assumed. |
| `eia_co2_per_kwh_petroleum`, `eia_us_average_co2_per_kwh` | only one vintage seen; range set to about +/-5 %. |
| `eia_coal_combustion_co2_per_mmbtu`, `eia_natural_gas_combustion_co2_per_mmbtu` | ranges assumed to span coal ranks / gas composition (+/-1.5-3 %). |
| `lca_*_ar5` | medians confirmed via secondary sources; min/max for nuclear, gas CC and coal are from knowledge of Table A.III.2 and must be checked. Hydro max 2200 is the AR5 reservoir outlier. |
| `jet_kerosene_co2_ef` | derived as carbon content x 44/12 with 100 % oxidation (IPCC default); FT-SPK is assumed to have the same per-MJ combustion CO2 as jet kerosene (to be revisited at M2 with FT-SPK carbon content). |
| `electrolysis_efficiency_lhv` | value = Concawe 2030 case (68 %) as the commissioning-era technology for a 2027-2030 plant; low = 2020 (66.5 %), high = 2050 (75 %). |
| `ft_synthesis_efficiency` | 73 % from the ICCT 2022 diagram; 65-80 % bounds assumed pending ICCT 2017 Table 3.2. |
| `ft_stoich_*` | ideal -CH2- stoichiometry; high bounds (3.6 kg CO2/kg, 0.55 kg H2/kg) are placeholders for tail-gas and selectivity losses, to be replaced by a plant mass balance at M2. |
| `dac_liquid_solvent_*` | Keith et al. (2018) electricity+gas configuration as the value; the all-gas configuration as the other bound. |
| `dac_solid_sorbent_*` | value = midpoint of the literature range (167-305 kWh_el, 1.4-3.2 MWh_th per t); to be replaced with IEA DAC 2022 figures. |
| `lcfs_jet_benchmark_2025` | 81.70 assumes the amended jet table mirrors the diesel table (CARB states that it does); the jet row itself was not seen. Full table pending. |
| `epa_hub_2025_*_freight` | low/high bounds taken from earlier Hub editions from knowledge; to be checked. |
| GWP basis | AR6 is the engine default; CORSIA and LCFS GWP choices are set per rulebook at M4. |

## 3. Pathway model (M2)

`efuel_ci.pathway.compute` builds the stage vector for 1 MJ of fuel (LHV) from registry factors only.

### 3.1 Stage definitions and formulas

| stage | formula (per MJ fuel) | factors |
|---|---|---|
| electrolysis | `(1/eta_FT) / eta_el / 3.6 kWh x CI_el` | `ft_synthesis_efficiency`, `electrolysis_efficiency_lhv` |
| co2_capture | CO2 demand `= ft_stoich_co2_per_kg_fuel / LHV`; energy per tCO2 by source (below) | `dac_*`, `co2_*`, `natural_gas_*` |
| ft_synthesis | 0 (see 3.2-A) | - |
| transport | `EF_mode [kg/ton-mile] x miles / (LHV x 907.18 kg/ton)` | `epa_hub_2025_*_freight` |
| combustion | `jet_kerosene_co2_ef` (or `gas_diesel_oil_co2_ef`) in g/MJ | |
| captured_co2_credit | `-combustion` if `co2_treatment == neutral`, else 0 | |

CO2 capture energy by source:
- `dac_solid_sorbent`: `dac_solid_sorbent_electricity` (kWh_el/t) + `dac_solid_sorbent_heat` (kWh_th/t) at ~100 C;
  the heat is supplied by `capture_heat_source`: `electric` (resistive, 1 kWh_el per kWh_th), `waste_heat`
  (FT exotherm, zero marginal emissions) or `natural_gas` (boiler at `gas_boiler_efficiency`, gas
  combustion + upstream counted).
- `dac_liquid_solvent` (Keith et al. 2018 design): `dac_liquid_solvent_electricity` + `dac_liquid_solvent_gas`;
  the gas is burned in the oxy-fired calciner whose CO2 is captured in-process, so only the gas
  supply-chain emissions (`natural_gas_upstream_ci x ng_hhv_to_lhv_ratio`) are counted.
- `point_source`: `co2_compression_electricity` plus, when `include_point_source_capture_heat`,
  `co2_point_source_capture_heat` (GJ/t) from `capture_heat_source`.

### 3.2 Assumptions (M2)

- **A. Synthesis energy is folded into the FT efficiency.** RWGS, FT, hydrocracking and compression are
  represented only by `ft_synthesis_efficiency` (fuel LHV / H2 LHV = 0.73, ICCT 2022). Plant auxiliary
  electricity for synthesis is not modelled separately (no cited figure reachable); it is an under-count
  of a few percent of plant electricity. The ICCT overall-efficiency band (46-51 %) is enforced as a test.
- **B. Carbon balance closes at the plant boundary.** CO2 demand is stoichiometric (3.14 kg/kg -CH2-);
  tail-gas carbon is assumed recycled, so captured CO2 == combusted CO2 (tested within 2 %). Any vented
  CO2 is of captured origin and therefore has the same treatment as combustion CO2.
- **C. FT-SPK is given jet kerosene's NCV (44.1 MJ/kg) and combustion factor (71.5 gCO2/MJ);** eDiesel uses
  gas/diesel oil values. Non-CO2 combustion emissions (CH4, N2O) are omitted (< 0.5 gCO2e/MJ).
- **D. Hydrogen mass balance is implied, not input:** 1/0.73 MJ H2 per MJ fuel gives 0.50 kg H2 per kg
  fuel, i.e. 86 % H2 utilisation against stoichiometry; the test checks it sits in the registry range.
- **E. All plant electricity (electrolysis, DAC, compression, resistive heat) carries one delivered CI**
  (`electricity_ci`, gCO2e/kWh); the electricity module (M3) supplies it.
- **F. `co2_treatment`** is the only rulebook-sensitive switch at this level: `neutral` nets combustion CO2
  against the captured carbon (DAC, biogenic, or point-source where the rulebook credits it);
  `fossil_attributed` counts combustion CO2 in full. Rulebooks (M4) choose per their rules.
- **G. Water, catalysts, plant construction (cradle) are excluded**; the model is well-to-wake operational.
- **H. Transport** uses a fixed distance per scenario by rail/truck/ship with EPA Hub factors (short-ton-miles).
- **I. DAC heat from FT exotherm** (`waste_heat`) assumes the FT reactor's low-pressure steam (~200 C) covers
  the ~100 C sorbent regeneration; it is a modelling choice common to LBST/Concawe-type studies, flagged.
- **J. HHV->LHV for natural gas** uses `ng_hhv_to_lhv_ratio` (1.10, unverified) when applying Balcombe's
  per-MJ-HHV supply-chain factor.

### 3.3 Energy/mass balance produced (central factors)

Per MJ eSAF, point-source CO2, central efficiencies: 1.370 MJ H2; 0.560 kWh electricity for electrolysis;
0.503 kg H2 and 3.14 kg CO2 per kg fuel; implied PtL efficiency (fuel LHV / electricity) 49.6 % before
capture energy, inside ICCT's 46-51 % band.

### 3.4 Published-figure checks (tests, +/-10 %)

1. **Concawe/Aramco e-fuels study, Concawe Review 33(1), May 2025:** cradle-to-grave ~5.5 gCO2eq/MJ for
   North-Europe e-FT fuels in 2050 (DAC CO2, renewable electricity, 75 % electrolysis). Our run:
   wind lifecycle CI 11 gCO2e/kWh (`lca_wind_onshore_ar5`), `electrolysis_efficiency_lhv` at its 2050
   high (0.75), Climeworks DAC with heat from FT waste heat, 300 rail-miles -> **5.94 gCO2e/MJ (+7.9 %)**.
   Gap: our electricity CI is a generic AR5 wind median (Concawe's North-EU mix and its own LCA factor
   were not visible), and Concawe's cradle-to-grave includes plant construction, which we exclude; with
   DAC heat supplied electrically the figure is 7.3 (+33 %), so the waste-heat assumption (I) is doing
   real work and is flagged.
2. **Liu, Sandhu, McCoy, Bergerson (2020), Sustainable Energy & Fuels 4:3129-3142:** the DAC + FT pathway
   beats conventional diesel only below **139 gCO2e/kWh**. Our breakeven with Keith-type DAC and the
   94 gCO2e/MJ fossil comparator: **152.8 gCO2e/kWh (+9.9 %)**; with 89 (CORSIA) 144.2 (+3.7 %).
   Gap: Liu's diesel comparator value was not visible (assumed 94); Liu used van der Giesen's FT and
   2018-era electrolysis, both less efficient than our 2030-case factors, which lowers their breakeven.
   This check passes only at the edge of +/-10 % and is reported as such.
   Their baseline 29 gCO2e/MJ could not be checked because the baseline grid factor is not stated in the
   reachable text.

## 4. Electricity module (M3)

`efuel_ci.electricity` provides (a) the annual ERCOT CI, (b) the hourly CI series and (c) contracted
clean power with annual / monthly / hourly matching.

### 4.1 Definitions

- **Generation vs delivered.** eGRID output rates and the EIA fuel mix are generation-based. The plant
  buys delivered power, so every CI used by the pathway is divided by `(1 - egrid2023_erct_grid_gross_loss)`.
- **Hourly CI (b)** = sum over fuel codes of (MWh_f x EF_f) / sum of MWh_f, per hour, using the EIA-930
  fuel-type series for respondent ERCO. Two bases:
  - `direct`: combustion-only per-fuel factors from EIA FAQ 74 (`eia_co2_per_kwh_coal|natural_gas|petroleum`);
    nuclear, wind, solar, hydro = 0. This is comparable to eGRID (the annual generation-weighted mean of the
    series is checked against the eGRID ERCT rate once real data are present).
  - `lifecycle`: IPCC AR5 Annex III medians per fuel (`lca_*_ar5`), including clean generation.
- **Matching (c).** Within each window (year, calendar month, or hour) the plant's load L_w is matched
  against contracted clean energy C_w: matched = min(L_w, C_w); residual = L_w - matched, charged at the
  window's load-weighted hourly grid CI; matched energy is charged `clean_ci` (0 on the direct basis).
  Surplus clean energy inside a window is not banked into other windows. With window = year this reduces
  exactly to CI = (1 - share) x annual load-weighted grid CI (tested).
- **Contracted profile.** `clean_profile` gives the hourly shape of the contracted supply (flat for a
  firm/baseload PPA; the ERCOT WND and/or SUN series for a wind/solar PPA); it is scaled so its annual energy
  equals `clean_share` x annual plant load. The plant load is flat (electrolyser at constant output) unless
  a series is given.
- **`clean_share_to_clear`** bisects on the share to find the smallest contracted clean fraction whose
  matched CI meets a target (used for the headline "Z %" at M5).

### 4.2 Assumptions (M3)

- **K. EIA fuel-code mapping.** COL -> coal, NG -> natural gas, OIL -> petroleum, OTH -> treated as natural
  gas (EIA "Other" is a mixed bag of biomass, waste, landfill gas and unspecified thermal; natural gas is
  the nearest cited factor), NUC/SUN/WAT/WND -> zero on the direct basis. Codes not in the table raise an
  error so new codes are classified deliberately. Only SUN, WAT, NG, OTH, NUC, WND were confirmed in EIA
  output this session; BAT/PS/UES are assumed to be storage codes if they appear.
- **L. Storage and negative values.** Storage codes are excluded from numerator and denominator (their
  discharge takes the hour's mix CI); negative generation values (net consumption) are clipped to zero.
- **M. Direct basis omits upstream** (methane from gas supply, coal mining). The lifecycle basis uses AR5
  per-technology medians instead; it is not "direct + upstream" (AR5 coal 820 is below the US fleet's
  direct 1,048 gCO2/kWh because it reflects modern plants). Rulebooks choose the basis at M4.
- **N. Loss factor** is the eGRID ERCT grid gross loss (4.2 %, provisional) applied uniformly to all hours.
- **O. Year alignment.** The hourly series year is 2024 (EIA) while the annual factor is eGRID2023; the
  generation-weighted mean of the 2024 series is reported alongside eGRID2023 so the vintage gap is visible.
- **P. Monthly residual** is spread over the month's hours in proportion to load (the rulebook only
  constrains the monthly balance), so a monthly-matched CI is the month's load-weighted grid CI times the
  month's residual fraction.

### 4.3 Status at M3: hourly data not yet downloaded

`scripts/download.py eia-hourly --year 2024` implements the EIA v2 route
`electricity/rto/fuel-type-data` (respondent ERCO, hourly, paged at 5,000 rows, retried with backoff) and
writes `data/raw/eia_erco_fueltype_2024.csv` plus a lineage manifest. It could not be run: api.eia.gov is
blocked by this environment's network policy and no `EIA_API_KEY` is set. The matching arithmetic is
therefore tested on a **synthetic, clearly labelled shape generator** (`tests/synthetic_mix.py`) that never
feeds results; `make run` reports the hourly block as `unavailable` until the real file exists. The annual
eGRID number is real: ERCOT 2023 332.9 gCO2/kWh at the busbar, 347.5 gCO2/kWh delivered.

## 5. Rulebook simplifications (M4) - to be written per rulebook

## 6. Scenarios and sensitivity (M5) - to be written
