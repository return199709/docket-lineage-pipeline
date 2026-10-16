# efuel-carbon-intensity — project instructions for Claude Code

## What this repo is
An auditable lifecycle carbon-intensity (CI) engine for power-to-liquid eFuels (eSAF, eDiesel).
Inputs: CO2 source, electricity source and temporal matching, hydrogen pathway, transport.
Output: gCO2e/MJ by stage, under three rulebooks (California LCFS, CORSIA, EU RFNBO), with a
citation for every factor and a lineage hash for every run.
Anchor company: Infinium (Project Roadrunner, West Texas). Variant: NZero (hourly vs annual Scope 2).

**Headline result the README must deliver:** "A West-Texas eFuel plant on grid power scores X gCO2e/MJ
under annual matching but Y under RFNBO hourly matching; it needs Z% contracted clean power to clear
the 70% reduction threshold." One chart: six scenarios vs the fossil-jet baseline and the three thresholds.

## Repo conventions (already in place from the template; do not change them)
- Python 3.12, `uv` for deps (`uv add <pkg>` to add; justify every new dependency in the commit message).
- `src/efuel_ci/` package, `tests/`, `scripts/download.py`, `data/raw` (gitignored except small samples),
  `results/` (gitignored). `make setup | lint | test | run` must all pass before every commit.
- `results/lineage.json` is written by `efuel_ci.lineage.Manifest` on every run; register every file read
  or written. Never print or commit secrets; keys come from `.env` via `efuel_ci.config.Settings`.
- README is result-first: the headline number and chart are the first thing a reader sees.
- Every simplification or assumption goes in `docs/methodology.md` the moment it is made, not later.

## Working agreements
1. Work one milestone at a time. Before coding, write a 5–10 line plan naming the files you will touch.
2. Write tests for pure functions first (factor lookups, stage calculations, rulebook adjustments).
3. Never fabricate a factor, a dataset or a result. If a source is unreachable, stop and report; do not
   substitute a guessed number silently. Approximate values below marked (verify) must be checked against
   the cited source and the citation recorded in the registry before use.
4. One commit per milestone, message `M<n>: <what>`; `make lint && make test && make run` green first.
5. At the end of each milestone, stop and report in the format at the bottom of this file. Do not start
   the next milestone until told to.

## Architecture to build
```
factors/                 YAML registries: electricity.yaml, process.yaml, transport.yaml, gwp.yaml
src/efuel_ci/
  registry.py            load + validate factors (pydantic): id, value, unit, low, high, source, url, vintage, notes
  electricity.py         electricity CI: annual average, hourly (EIA Grid Monitor), contracted + matching
  pathway.py             stage model: H2 electrolysis, CO2 capture, FT synthesis, upgrading, transport, combustion
  rulebooks/
    base.py              Rulebook interface: adjust(stages, inputs) -> CI, threshold(), comparator()
    lcfs.py  corsia.py  rfnbo.py
  scenarios.py           six named scenarios; runner -> DataFrame (scenario x rulebook x stage)
  sensitivity.py         one-at-a-time tornado over the registry ranges
  scope2.py              NZero variant: hourly-matched vs annual-average Scope 2 for a building load series
  plots.py               headline chart (matplotlib, saved to docs/headline.png)
  pipeline.py            run(): scenarios -> results/summary.json + lineage
app/streamlit_app.py     scenario explorer
docs/methodology.md      every assumption, with the rulebook simplifications listed per rulebook
docs/adaptation_notes/   NZero.md, Joulent.md, Arcadia.md (use TEMPLATE.md)
```

## Data sources (use these; add others only with a citation)
- EIA API v2, hourly generation by fuel type for ERCOT (`electricity/rto/fuel-type-data`, respondent ERCO);
  needs `EIA_API_KEY` (free). Download one full calendar year via `scripts/download.py`.
- EPA eGRID for annual grid factors; EPA / IPCC AR6 GWP-100 values; fuel combustion factors from EPA.
- Process energy balances for electrolysis, CO2 capture and Fischer-Tropsch from ICCT and Concawe eFuel
  reports and GREET documentation (cite report, table, page). Carry low/high ranges, not single points.
- Building Data Genome 2 (GitHub: buds-lab) for the Scope 2 variant; pick 3 buildings in a US grid region
  that EIA covers hourly.
- Rulebook thresholds and comparators: look them up and cite the primary document. Starting points to
  verify: RFNBO 70% reduction vs a fossil comparator around 94 gCO2e/MJ (verify), temporal correlation
  monthly then hourly (verify dates); CORSIA baseline ~89 gCO2e/MJ with 10% minimum reduction (verify);
  LCFS CI benchmarks are annual and declining — fetch the current table (verify).

## Milestones
**M1 — Factor registry.** YAML schema + loader + validation; at least 25 factors with citations and ranges;
`registry.list()` prints a citation table. Tests: schema rejects missing citation/unit; lookups work.
Acceptance: `make test` green; `docs/methodology.md` created with the registry rules.

**M2 — Pathway model.** Stage-by-stage energy and mass balance for 1 MJ of eSAF; CI by stage with a
biogenic/captured-CO2 treatment flag. Reproduce one published eFuel CI figure (ICCT or Concawe) within ±10%
and record which figure and why any gap. Tests: stage sums, unit conversions, published-figure check.

**M3 — Electricity module.** (a) annual average CI for ERCOT from EIA + eGRID; (b) hourly CI series from
EIA fuel mix × factors; (c) contracted clean power with annual, monthly and hourly matching, residual filled
from the hourly grid series. Tests: hourly series length = hours in year, no NaNs, matching reduces to
annual case when matching window = year.

**M4 — Rulebooks.** Three rulebook classes with `adjust`, `threshold`, `comparator`, each with its
simplifications listed in methodology.md. Tests: each rulebook on a fixed stage vector gives a documented
number; threshold comparison returns pass/fail.

**M5 — Scenarios, sensitivity, headline.** Six scenarios (grid annual, grid hourly, 50/80/100% contracted
clean with hourly matching, DAC + 100% clean). Tornado over factor ranges. `make run` writes
`results/summary.json` with CI per scenario × rulebook and the clean-power share needed to clear RFNBO;
`docs/headline.png` produced. README updated with real numbers.

**M6 — Scope 2 variant.** `scope2.py` on three BDG2 buildings: hourly-matched vs annual-average tCO2 and
gap %. Written up as `docs/adaptation_notes/NZero.md` with a chart.

**M7 — App and write-up.** Streamlit app with scenario sliders; methodology.md complete; adaptation notes
for Joulent and Arcadia; README final with run instructions, data table and lineage section.

## Definition of done
- Clean clone: `make setup && make run` reproduces `results/summary.json` and `docs/headline.png`.
- Every number in the README traces to a factor id in `factors/` and a hash in `results/lineage.json`.
- Published-figure check within ±10% is a passing test, not a sentence.
- CI (GitHub Actions) is green on `main`.

## End-of-milestone report format
```
Milestone: M<n>
Done: <bullets>
Files: <added/changed>
Numbers produced: <any result values, with factor ids>
Assumptions added to methodology.md: <list>
Open questions for you: <list, or "none">
Next: M<n+1> plan in 3 lines
```
