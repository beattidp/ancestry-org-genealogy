"""Unit tests for deterministic biological and chronological constraint validation."""

import pytest
from src.constraints.date_parser import (
    DateEstimate,
    calculate_age_in_years,
    calculate_days_between,
    parse_date,
)
from src.constraints.engine import ConstraintEngine
from src.constraints.rules import (
    check_individual_chronology,
    check_parent_child_biology,
    check_spousal_chronology,
)
from src.storage.db import Database


# ---------------------------------------------------------------------------
# Date Parser Tests
# ---------------------------------------------------------------------------


def test_date_parser_formal_iso():
    d = parse_date(date_formal="+1966-04-21")
    assert d is not None
    assert d.year == 1966
    assert d.month == 4
    assert d.day == 21
    assert d.exact_date is not None
    assert str(d) == "1966-04-21"

    d_mo = parse_date(date_formal="+1937-07")
    assert d_mo is not None
    assert d_mo.year == 1937
    assert d_mo.month == 7
    assert d_mo.day is None
    assert str(d_mo) == "1937-07"

    d_yr = parse_date(date_formal="+1930")
    assert d_yr is not None
    assert d_yr.year == 1930
    assert d_yr.month is None
    assert str(d_yr) == "1930"

    d_rng = parse_date(date_formal="+1880/+1885")
    assert d_rng is not None
    assert d_rng.min_year == 1880
    assert d_rng.max_year == 1885
    assert d_rng.is_approximate is True


def test_date_parser_original_text():
    d1 = parse_date(date_original="22 November 1919")
    assert d1 is not None
    assert d1.year == 1919
    assert d1.month == 11
    assert d1.day == 22
    assert d1.exact_date is not None

    d2 = parse_date(date_original="19660421")
    assert d2 is not None
    assert d2.year == 1966
    assert d2.month == 4
    assert d2.day == 21

    d3 = parse_date(date_original="Jul 1937")
    assert d3 is not None
    assert d3.year == 1937
    assert d3.month == 7

    d4 = parse_date(date_original="about 1850")
    assert d4 is not None
    assert d4.year == 1850
    assert d4.is_approximate is True


def test_date_arithmetic():
    b = parse_date(date_formal="+1919-11-22")
    d = parse_date(date_formal="+2000-03-24")
    age = calculate_age_in_years(b, d)
    assert age is not None
    assert 80.0 <= age <= 80.5

    days = calculate_days_between(b, d)
    assert days is not None
    assert days > 29000


# ---------------------------------------------------------------------------
# Individual Chronology Rules
# ---------------------------------------------------------------------------


def test_individual_chronology_normal():
    person = {"pid": "P1", "birth_date": "1920-01-01", "death_date": "1995-05-10"}
    facts = []
    v = check_individual_chronology(person, facts)
    assert len(v) == 0


def test_individual_chronology_death_before_birth():
    person = {"pid": "P1", "birth_date": "1920-01-01", "death_date": "1910-01-01"}
    facts = []
    v = check_individual_chronology(person, facts)
    assert len(v) == 1
    assert v[0].rule_id == "CHRONO-EVENT-ORDER"
    assert v[0].severity == "ERROR"


def test_individual_chronology_centenarian_and_exceeded():
    # Centenarian warning
    person_cent = {"pid": "P1", "birth_date": "1900-01-01", "death_date": "2008-01-01"}
    v_cent = check_individual_chronology(person_cent, [])
    assert len(v_cent) == 1
    assert v_cent[0].rule_id == "CHRONO-LIFESPAN"
    assert v_cent[0].severity == "WARNING"

    # Impossible age (> 120)
    person_imp = {"pid": "P2", "birth_date": "1800-01-01", "death_date": "1930-01-01"}
    v_imp = check_individual_chronology(person_imp, [])
    assert len(v_imp) == 1
    assert v_imp[0].rule_id == "CHRONO-LIFESPAN"
    assert v_imp[0].severity == "ERROR"


# ---------------------------------------------------------------------------
# Parent-Child Biology Rules
# ---------------------------------------------------------------------------


def test_parent_child_mother_age_limits():
    # Mother too young (< 13)
    mother_young = {"pid": "M1", "gender": "Female", "birth_date": "1900-01-01", "death_date": "1960-01-01"}
    child = {"pid": "C1", "birth_date": "1911-06-01", "death_date": "1980-01-01"}
    v = check_parent_child_biology(mother_young, child, "mother", [], [])
    assert any(vi.rule_id == "BIO-MOTH-AGE" and vi.severity == "ERROR" for vi in v)

    # Mother too old (> 50)
    mother_old = {"pid": "M2", "gender": "Female", "birth_date": "1880-01-01", "death_date": "1960-01-01"}
    child_old = {"pid": "C2", "birth_date": "1935-01-01", "death_date": "2000-01-01"}
    v_old = check_parent_child_biology(mother_old, child_old, "mother", [], [])
    assert any(vi.rule_id == "BIO-MOTH-AGE" and vi.severity == "ERROR" for vi in v_old)

    # Mother normal age (28)
    mother_norm = {"pid": "M3", "gender": "Female", "birth_date": "1900-01-01", "death_date": "1960-01-01"}
    child_norm = {"pid": "C3", "birth_date": "1928-01-01", "death_date": "2000-01-01"}
    v_norm = check_parent_child_biology(mother_norm, child_norm, "mother", [], [])
    assert len(v_norm) == 0


def test_parent_child_posthumous():
    # Mother died before child birth
    mother = {"pid": "M1", "gender": "Female", "birth_date": "1900-01-01", "death_date": "1925-01-01"}
    child_post = {"pid": "C1", "birth_date": "1927-01-01", "death_date": "2000-01-01"}
    v_moth = check_parent_child_biology(mother, child_post, "mother", [], [])
    assert any(vi.rule_id == "BIO-MOTH-POSTHUMOUS" and vi.severity == "ERROR" for vi in v_moth)

    # Father died 400 days before child birth (> 280 days)
    father = {"pid": "F1", "gender": "Male", "birth_date": "1900-01-01", "death_date": "1930-01-01"}
    child_fath = {"pid": "C2", "birth_date": "1931-03-01", "death_date": "2000-01-01"}
    v_fath = check_parent_child_biology(father, child_fath, "father", [], [])
    assert any(vi.rule_id == "BIO-FATH-POSTHUMOUS" and vi.severity == "ERROR" for vi in v_fath)


def test_parent_child_relational_inversion():
    parent = {"pid": "P1", "gender": "Male", "birth_date": "1930-01-01", "death_date": "2000-01-01"}
    child = {"pid": "C1", "birth_date": "1910-01-01", "death_date": "1980-01-01"}
    v = check_parent_child_biology(parent, child, "father", [], [])
    assert len(v) == 1
    assert v[0].rule_id == "REL-INVERSION"
    assert v[0].severity == "ERROR"


# ---------------------------------------------------------------------------
# Spousal Chronology Rules
# ---------------------------------------------------------------------------


def test_spousal_chronology():
    husband = {"pid": "H1", "gender": "Male", "birth_date": "1900-01-01", "death_date": "1970-01-01"}
    wife = {"pid": "W1", "gender": "Female", "birth_date": "1902-01-01", "death_date": "1975-01-01"}

    # Marriage at age 10 for wife
    marr_young = {"date_formal": "+1912-06-01"}
    v = check_spousal_chronology(husband, wife, marr_young, [], [])
    assert any(vi.rule_id == "CHRONO-MARR-AGE" and vi.severity == "ERROR" for vi in v)

    # Marriage after husband death
    marr_post = {"date_formal": "+1972-06-01"}
    v_post = check_spousal_chronology(husband, wife, marr_post, [], [])
    assert any(vi.rule_id == "CHRONO-EVENT-ORDER" and vi.severity == "ERROR" for vi in v_post)


# ---------------------------------------------------------------------------
# Constraint Engine End-to-End
# ---------------------------------------------------------------------------


def test_constraint_engine_e2e(tmp_path):
    db_path = tmp_path / "test_constraints.sqlite"
    db = Database(str(db_path))

    # Insert test persons
    db.upsert_person({
        "pid": "P_CHILD",
        "name": "Test Child",
        "gender": "Male",
        "birth_date": "1950-01-01",
        "death_date": "2020-01-01",
    })
    db.upsert_person({
        "pid": "P_MOTHER",
        "name": "Test Mother",
        "gender": "Female",
        "birth_date": "1945-01-01",  # Mother aged 5 at child birth -> ERROR
        "death_date": "2010-01-01",
    })

    # Insert parent-child relationship
    db.upsert_relationships_batch([{
        "id": "rel1",
        "relationship_type": "parent-child",
        "parent_pid": "P_MOTHER",
        "child_pid": "P_CHILD",
        "lineage_type": "biological",
    }])

    # Run engine
    engine = ConstraintEngine(db)
    report = engine.validate(persist=True)

    assert report.total_persons == 2
    assert report.error_count >= 1
    assert report.pass_rate < 100.0
    assert any(v.rule_id == "BIO-MOTH-AGE" for v in report.violations)

    # Verify violations were stored in SQLite
    stored_violations = db.get_violations()
    assert len(stored_violations) >= 1
    assert stored_violations[0]["rule_id"] == "BIO-MOTH-AGE"
