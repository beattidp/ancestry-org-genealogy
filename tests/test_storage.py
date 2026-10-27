"""Unit tests for SQLite storage manager."""

import tempfile
from pathlib import Path
import pytest
from src.storage.db import Database


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_pedigree.sqlite"
        yield Database(db_path)


def test_db_initialization(temp_db):
    with temp_db.get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
        table_names = [t["name"] for t in tables]

    assert "persons" in table_names
    assert "relationships" in table_names
    assert "pedigree_tree" in table_names
    assert "facts" in table_names
    assert "ingestion_runs" in table_names


def test_upsert_person(temp_db):
    person = {
        "pid": "P001",
        "name": "Jane Doe",
        "gender": "Female",
        "lifespan": "1890-1970",
        "living": False,
        "birth_date": "1890-05-12",
        "birth_place": "Boston, MA",
        "death_date": "1970-11-20",
        "death_place": "New York, NY",
        "raw_json": {"id": "P001", "name": "Jane Doe"},
    }
    temp_db.upsert_person(person)
    retrieved = temp_db.get_person("P001")
    assert retrieved is not None
    assert retrieved["name"] == "Jane Doe"
    assert retrieved["living"] == 0

    # Test update on conflict
    person["name"] = "Jane Smith"
    temp_db.upsert_person(person)
    updated = temp_db.get_person("P001")
    assert updated["name"] == "Jane Smith"


def test_pedigree_tree_and_stats(temp_db):
    # Insert root and parents
    p1 = {"pid": "P001", "name": "Child", "gender": "Male"}
    p2 = {"pid": "P002", "name": "Father", "gender": "Male"}
    p3 = {"pid": "P003", "name": "Mother", "gender": "Female"}
    temp_db.upsert_persons_batch([p1, p2, p3])

    temp_db.upsert_pedigree_node("P001", "P001", generation=0, ascendancy_number=1, lineage_path="self")
    temp_db.upsert_pedigree_node("P001", "P002", generation=1, ascendancy_number=2, lineage_path="father")
    temp_db.upsert_pedigree_node("P001", "P003", generation=1, ascendancy_number=3, lineage_path="mother")

    pedigree = temp_db.get_pedigree("P001")
    assert len(pedigree) == 3
    assert pedigree[0]["pid"] == "P001"
    assert pedigree[1]["pid"] == "P002"

    stats = temp_db.get_pedigree_stats("P001")
    assert stats["total_ancestors"] == 3
    assert stats["generations"][0]["count"] == 1
    assert stats["generations"][1]["count"] == 2
    assert stats["generations"][1]["completeness"] == 100.0


def test_pedigree_gaps(temp_db):
    # Child has father, but mother is missing
    p1 = {"pid": "P001", "name": "Child", "gender": "Male"}
    p2 = {"pid": "P002", "name": "Father", "gender": "Male"}
    temp_db.upsert_persons_batch([p1, p2])
    temp_db.upsert_pedigree_node("P001", "P001", generation=0, ascendancy_number=1)
    temp_db.upsert_pedigree_node("P001", "P002", generation=1, ascendancy_number=2)

    temp_db.upsert_relationship(
        {"id": "rel1", "rel_type": "parent-child", "parent_pid": "P002", "child_pid": "P001"}
    )

    gaps = temp_db.get_pedigree_gaps("P001", max_generation=2)
    # Child should be flagged as missing Mother
    child_gap = next((g for g in gaps if g["pid"] == "P001"), None)
    assert child_gap is not None
    assert "Mother" in child_gap["missing"]
    assert "Father" not in child_gap["missing"]
