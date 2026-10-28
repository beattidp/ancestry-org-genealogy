"""Unit tests for GEDCOM 5.5.1 export engine."""

from typing import Any
import pytest

from src.gedcom.exporter import (
    GedcomExporter,
    clean_gedcom_text,
    clean_pointer_id,
    format_gedcom_name,
)
from src.storage.db import Database


@pytest.fixture
def temp_db(tmp_path: Any) -> Database:
    """Fixture providing an isolated SQLite database."""
    db_file = tmp_path / "test_pedigree.sqlite"
    return Database(db_path=db_file)


def test_format_gedcom_name() -> None:
    full, givn, surn, nsfx = format_gedcom_name("Douglas Paul Miller Jr")
    assert full == "Douglas Paul /Miller/ Jr"
    assert givn == "Douglas Paul"
    assert surn == "Miller"
    assert nsfx == "Jr"

    full2, givn2, surn2, nsfx2 = format_gedcom_name("Adam Smith")
    assert full2 == "Adam /Smith/"
    assert givn2 == "Adam"
    assert surn2 == "Smith"
    assert nsfx2 == ""

    full3, givn3, surn3, nsfx3 = format_gedcom_name("Smith")
    assert full3 == "/Smith/"
    assert givn3 == ""
    assert surn3 == "Smith"

    full4, givn4, surn4, nsfx4 = format_gedcom_name("")
    assert full4 == "Unknown //"


def test_clean_gedcom_text() -> None:
    raw = "Line 1\r\nLine 2\twith tabs and \x00nulls"
    cleaned = clean_gedcom_text(raw)
    assert "\r" not in cleaned
    assert "\n" not in cleaned
    assert "\t" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "Line 1 Line 2 with tabs and nulls"


def test_clean_pointer_id() -> None:
    assert clean_pointer_id("PID-1234", prefix="I") == "@I_PID_1234@"
    assert clean_pointer_id("SRC-1234.5", prefix="S") == "@S_SRC_1234_5@"


def test_gedcom_export_lineage_linked(temp_db: Database, tmp_path: Any) -> None:
    # 1. Insert Father, Mother, Child
    father = {
        "pid": "P-FATHER",
        "name": "Adam Smith",
        "gender": "Male",
        "birth_date": "1828",
        "birth_place": "Ireland",
        "death_date": "1908",
        "death_place": "Sonoma, California",
        "living": 0,
    }
    mother = {
        "pid": "P-MOTHER",
        "name": "Catherine Kennedy",
        "gender": "Female",
        "birth_date": "1830",
        "birth_place": "Ireland",
        "living": 0,
    }
    child = {
        "pid": "P-CHILD",
        "name": "John A K Smith",
        "gender": "Male",
        "birth_date": "1853",
        "living": 0,
    }

    temp_db.upsert_person(father)
    temp_db.upsert_person(mother)
    temp_db.upsert_person(child)

    # 2. Insert Pedigree tree entries
    with temp_db.get_connection() as conn:
        conn.execute(
            "INSERT INTO pedigree_tree (root_pid, person_pid, generation, ascendancy_number) VALUES (?, ?, ?, ?)",
            ("P-CHILD", "P-CHILD", 0, 1),
        )
        conn.execute(
            "INSERT INTO pedigree_tree (root_pid, person_pid, generation, ascendancy_number) VALUES (?, ?, ?, ?)",
            ("P-CHILD", "P-FATHER", 1, 2),
        )
        conn.execute(
            "INSERT INTO pedigree_tree (root_pid, person_pid, generation, ascendancy_number) VALUES (?, ?, ?, ?)",
            ("P-CHILD", "P-MOTHER", 1, 3),
        )

        # 3. Insert relationships
        conn.execute(
            "INSERT INTO relationships (id, rel_type, parent_pid, child_pid) VALUES ('R1', 'parent-child', 'P-FATHER', 'P-CHILD')"
        )
        conn.execute(
            "INSERT INTO relationships (id, rel_type, parent_pid, child_pid) VALUES ('R2', 'parent-child', 'P-MOTHER', 'P-CHILD')"
        )
        conn.execute(
            "INSERT INTO relationships (id, rel_type, spouse1_pid, spouse2_pid) VALUES ('R3', 'couple', 'P-FATHER', 'P-MOTHER')"
        )

        # 4. Insert facts
        conn.execute(
            "INSERT INTO facts (person_pid, fact_type, date_original, place_normalized) VALUES ('P-FATHER', 'Birth', 'about 1828', 'Ireland')"
        )
        conn.execute(
            "INSERT INTO facts (person_pid, fact_type, date_original, place_normalized) VALUES ('P-FATHER', 'Death', '19 Jan 1908', 'Sonoma, California, United States')"
        )

        # 5. Insert source
        conn.execute(
            "INSERT INTO sources (id, title, about_url, citation_text) VALUES ('S-101', 'Sonoma County Records', 'https://example.com/record', 'Vol 4, p 12')"
        )
        conn.execute(
            "INSERT INTO person_sources (id, person_pid, source_id) VALUES ('PS-1', 'P-FATHER', 'S-101')"
        )

    # 6. Export to string
    exporter = GedcomExporter(db=temp_db)
    content, stats = exporter.export_to_string()

    # Validate stats
    assert stats["individuals"] == 3
    assert stats["families"] == 1
    assert stats["sources"] == 1

    # Validate GEDCOM syntax
    lines = content.strip().split("\n")
    assert lines[0] == "0 HEAD"
    assert "1 GEDC" in lines
    assert "2 VERS 5.5.1" in lines
    assert "2 FORM LINEAGE-LINKED" in lines
    assert "1 CHAR UTF-8" in lines
    assert lines[-1] == "0 TRLR"

    # Validate INDI tags
    assert "0 @I_P_FATHER@ INDI" in lines
    assert "1 NAME Adam /Smith/" in lines
    assert "1 SEX M" in lines
    assert "1 BIRT" in lines
    assert "2 DATE about 1828" in lines
    assert "2 PLAC Ireland" in lines
    assert "1 DEAT" in lines
    assert "2 DATE 19 Jan 1908" in lines
    assert "1 FAMS @F1@" in lines
    assert "1 SOUR @S_S_101@" in lines

    # Validate Child links
    assert "0 @I_P_CHILD@ INDI" in lines
    assert "1 FAMC @F1@" in lines

    # Validate FAM record
    assert "0 @F1@ FAM" in lines
    assert "1 HUSB @I_P_FATHER@" in lines
    assert "1 WIFE @I_P_MOTHER@" in lines
    assert "1 CHIL @I_P_CHILD@" in lines

    # Validate SOUR record
    assert "0 @S_S_101@ SOUR" in lines
    assert "1 TITL Sonoma County Records" in lines
    assert "1 NOTE URL: https://example.com/record" in lines

    # Test file export
    out_file = tmp_path / "test.ged"
    file_stats = exporter.export_to_file(out_file)
    assert out_file.exists()
    assert file_stats == stats
