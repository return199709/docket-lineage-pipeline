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

## 3. Pathway model (M2) - to be written

## 4. Electricity module (M3) - to be written

## 5. Rulebook simplifications (M4) - to be written per rulebook

## 6. Scenarios and sensitivity (M5) - to be written
