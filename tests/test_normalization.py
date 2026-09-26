from gridlock_pipeline.models import ConfidenceLevel
from gridlock_pipeline.normalization.dates import parse_in_service_year
from gridlock_pipeline.normalization.lengths import extract_lengths
from gridlock_pipeline.normalization.locations import extract_candidate_locations
from gridlock_pipeline.normalization.names import normalize_project_name
from gridlock_pipeline.normalization.organizations import (
    extract_owner_prefix,
    normalize_balancing_authority,
)
from gridlock_pipeline.normalization.project_type import classify_project_type
from gridlock_pipeline.normalization.voltage import extract_voltage


def test_voltage_extracts_slash_levels_not_conductor_or_temperature() -> None:
    raw, values, provenance = extract_voltage(
        "Replace 230/115 kV bank with 795 ACSR conductor rated at 100°C."
    )

    assert raw == ["230/115 kV"]
    assert values == [230.0, 115.0]
    assert provenance.rule_id == "voltage_kv_v1"


def test_name_normalization_preserves_identifiers_and_phase() -> None:
    value, provenance = normalize_project_name(
        "  SOCO: GAINESVILLE #2 – BULL SHOALS — PHASE 2  "
    )

    assert value == "SOCO: GAINESVILLE #2 - BULL SHOALS - PHASE 2"
    assert provenance.origin == "normalized"


def test_organization_rules_keep_authority_and_prefix_separate() -> None:
    authority, authority_provenance = normalize_balancing_authority(" southern ")
    prefix, prefix_provenance = extract_owner_prefix("GTC: EAST WALTON 500/230 KV PROJECT")

    assert authority == "SOUTHERN"
    assert authority_provenance.source_fields == ["balancing_authority_raw"]
    assert prefix == "GTC:"
    assert prefix_provenance.source_fields == ["project_name_raw"]


def test_project_type_is_deterministic_and_explainable() -> None:
    value, confidence, method, provenance = classify_project_type(
        "ALPHA - BETA 230 KV TRANSMISSION LINE, REBUILD",
        "Rebuild five miles of line.",
    )

    assert value == "line_rebuild"
    assert confidence == ConfidenceLevel.HIGH
    assert method == "project_type_rules_v1"
    assert provenance.origin == "deterministic_rule"


def test_lengths_preserve_multiple_independent_values() -> None:
    raw, values, provenance = extract_lengths(
        "Rebuild 8.1 miles and 8.2 miles of separate circuits."
    )

    assert raw == ["8.1 miles", "8.2 miles"]
    assert values == [8.1, 8.2]
    assert provenance.rule_id == "length_miles_v1"


def test_locations_are_conservative_candidates_without_geocoding() -> None:
    mentions, endpoints, provenance = extract_candidate_locations(
        "GTC: ADAMSVILLE - BUZZARD ROOST 230 KV REBUILD"
    )

    assert mentions == ["ADAMSVILLE", "BUZZARD ROOST"]
    assert endpoints == ["ADAMSVILLE", "BUZZARD ROOST"]
    assert provenance.rule_id == "location_candidates_v1"


def test_in_service_year_only_accepts_explicit_four_digit_year() -> None:
    year, provenance = parse_in_service_year("2029")
    unknown, unknown_provenance = parse_in_service_year("TBD")

    assert year == 2029
    assert provenance.rule_id == "in_service_year_v1"
    assert unknown is None
    assert unknown_provenance is None
