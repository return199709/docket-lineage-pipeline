"""M1 tests: schema validation, lookups, citation table, verification gate."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from efuel_ci.registry import (
    Factor,
    Registry,
    RegistryError,
    VerificationStatus,
    load_registry,
)


def test_good_factor_validates(good_factor):
    f = Factor(**good_factor)
    assert f.id == "test_factor"
    assert f.is_verified
    assert "example.org" in f.citation()


@pytest.mark.parametrize(
    "missing", ["source", "unit", "url", "vintage", "verification", "low", "high"]
)
def test_schema_rejects_missing_required_field(good_factor, missing):
    good_factor.pop(missing)
    with pytest.raises(ValidationError):
        Factor(**good_factor)


def test_schema_rejects_empty_citation_and_unit(good_factor):
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "source": ""})
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "unit": ""})


def test_schema_rejects_bad_url_and_unknown_fields(good_factor):
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "url": "not a url"})
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "extra_field": 1})


def test_schema_rejects_value_outside_range(good_factor):
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "value": 5.0})
    with pytest.raises(ValidationError):
        Factor(**{**good_factor, "low": 2.5})


def test_schema_rejects_bad_verification_status(good_factor):
    with pytest.raises(ValidationError):
        Factor(
            **{
                **good_factor,
                "verification": {"status": "trust me", "date": "2026-10-16", "method": "x"},
            }
        )


def test_duplicate_ids_rejected(good_factor):
    f = Factor(**good_factor)
    with pytest.raises(RegistryError):
        Registry([f, f])


def test_load_from_yaml_dir(tmp_path: Path, good_factor):
    (tmp_path / "x.yaml").write_text(
        textwrap.dedent(
            """
            category: test
            factors:
              - id: a_factor
                name: A factor
                value: 1.5
                unit: g/MJ
                low: 1.0
                high: 2.0
                source: "Doc (2020), Table 2"
                url: https://example.org/doc
                vintage: 2020
                verification: {status: secondary, date: 2026-10-16, method: quoted}
            """
        )
    )
    reg = load_registry(tmp_path)
    assert len(reg) == 1
    assert reg.get("a_factor").category == "test"
    assert reg.value("a_factor") == 1.5
    assert reg.value("a_factor", unit="g/MJ") == 1.5
    with pytest.raises(RegistryError):
        reg.value("a_factor", unit="kg/MJ")
    assert reg.range("a_factor") == (1.0, 1.5, 2.0)


def test_load_rejects_missing_citation_in_yaml(tmp_path: Path):
    (tmp_path / "x.yaml").write_text(
        textwrap.dedent(
            """
            category: test
            factors:
              - id: no_source
                name: No source
                value: 1.0
                unit: g/MJ
                low: 1.0
                high: 1.0
                url: https://example.org/doc
                vintage: 2020
                verification: {status: primary, date: 2026-10-16, method: x}
            """
        )
    )
    with pytest.raises(RegistryError, match="no_source"):
        load_registry(tmp_path)


def test_empty_dir_rejected(tmp_path: Path):
    with pytest.raises(RegistryError):
        load_registry(tmp_path)


# ---- the real registry ----------------------------------------------------


def test_real_registry_has_at_least_25_factors(registry: Registry):
    assert len(registry) >= 25


def test_real_registry_categories(registry: Registry):
    cats = {f.category for f in registry}
    assert cats == {"electricity", "process", "transport", "gwp"}


def test_real_registry_every_factor_has_range_and_citation(registry: Registry):
    for f in registry:
        assert f.low <= f.value <= f.high, f.id
        assert len(f.source) >= 10, f.id
        assert str(f.url).startswith("http"), f.id


def test_real_registry_lookups(registry: Registry):
    assert registry.value("corsia_baseline_jet", unit="gCO2e/MJ") == 89
    assert registry.value("rfnbo_fossil_comparator", unit="gCO2e/MJ") == 94
    assert registry.value("rfnbo_min_savings", unit="fraction") == 0.70
    assert registry.value("jet_kerosene_ncv", unit="MJ/kg") == 44.1
    assert registry.value("h2_lhv", unit="MJ/kg") == 120.0
    assert "unknown" not in registry
    with pytest.raises(RegistryError):
        registry.get("does_not_exist")


def test_derived_factors_are_consistent(registry: Registry):
    # jet CO2 factor = carbon content x 44/12
    c = registry.value("jet_kerosene_carbon_content", unit="tC/TJ")
    assert registry.value("jet_kerosene_co2_ef", unit="kgCO2/TJ") == pytest.approx(
        c * 44 / 12 * 1000, rel=1e-3
    )
    # electrolysis specific energy = LHV / efficiency
    lhv_kwh = registry.value("h2_lhv", unit="MJ/kg") / 3.6
    eff = registry.value("electrolysis_efficiency_lhv", unit="fraction")
    assert registry.value("electrolysis_specific_energy", unit="kWh/kgH2") == pytest.approx(
        lhv_kwh / eff, rel=0.01
    )
    # FT stoichiometry
    assert registry.value("ft_stoich_co2_per_kg_fuel") == pytest.approx(44.01 / 14.03, rel=0.01)
    assert registry.value("ft_stoich_h2_per_kg_fuel") == pytest.approx(3 * 2.016 / 14.03, rel=0.01)


def test_verification_gate(registry: Registry):
    unverified = [f.id for f in registry.by_status(VerificationStatus.UNVERIFIED)]
    assert unverified, "expected some factors still flagged unverified at M1"
    registry.require_verified(["corsia_baseline_jet", "jet_kerosene_ncv"])  # ok
    with pytest.raises(RegistryError, match=unverified[0]):
        registry.require_verified([unverified[0]])


def test_citation_table_formats(registry: Registry):
    table = registry.list("table")
    md = registry.list("markdown")
    csv_text = registry.list("csv")
    for fid in registry.ids():
        assert fid in table and fid in md and fid in csv_text
    assert "verification:" in table
    assert md.startswith("| id |")
    assert csv_text.splitlines()[0].startswith("id,category,value,unit")
