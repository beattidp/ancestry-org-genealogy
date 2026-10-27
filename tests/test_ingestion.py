"""Unit tests for pedigree extractor and ingester."""

import tempfile
from pathlib import Path
import pytest
from src.pedigree.extractor import (
    calculate_generation_and_path,
    calculate_global_ahnentafel,
    derive_pedigree_parent_child_relationships,
    extract_facts,
    extract_person,
    extract_relationships,
)
from src.pedigree.ingest import PedigreeIngester
from src.storage.db import Database


def test_calculate_generation_and_path():
    # Ahnentafel 1 = root person
    gen, path = calculate_generation_and_path(1)
    assert gen == 0
    assert path == "self"

    # Ahnentafel 2 = Father
    gen, path = calculate_generation_and_path(2)
    assert gen == 1
    assert path == "father"

    # Ahnentafel 3 = Mother
    gen, path = calculate_generation_and_path(3)
    assert gen == 1
    assert path == "mother"

    # Ahnentafel 4 = Father's father (Paternal Grandfather)
    gen, path = calculate_generation_and_path(4)
    assert gen == 2
    assert path == "father.father"

    # Ahnentafel 7 = Mother's mother (Maternal Grandmother)
    gen, path = calculate_generation_and_path(7)
    assert gen == 2
    assert path == "mother.mother"


def test_extract_person():
    raw_person = {
        "id": "KW12-345",
        "living": False,
        "display": {
            "name": "Thomas Jefferson",
            "gender": "Male",
            "lifespan": "1743-1826",
            "birthDate": "13 April 1743",
            "birthPlace": "Shadwell, Virginia",
            "deathDate": "4 July 1826",
            "deathPlace": "Monticello, Virginia",
        },
        "facts": [
            {
                "type": "http://gedcomx.org/Birth",
                "date": {"original": "13 April 1743", "formal": "+1743-04-13"},
                "place": {"original": "Shadwell, Virginia"},
            }
        ],
    }

    person = extract_person(raw_person)
    assert person["pid"] == "KW12-345"
    assert person["name"] == "Thomas Jefferson"
    assert person["gender"] == "Male"
    assert person["birth_date"] == "13 April 1743"
    assert not person["living"]

    facts = extract_facts(raw_person)
    assert len(facts) == 1
    assert facts[0]["fact_type"] == "Birth"
    assert facts[0]["date_formal"] == "+1743-04-13"


def test_extract_relationships():
    raw_rels = [
        {
            "id": "rel_100",
            "child": {"resourceId": "C01"},
            "father": {"resourceId": "F01"},
            "mother": {"resourceId": "M01"},
        }
    ]
    extracted = extract_relationships(raw_rels)
    # Expect 3 relationships: 2 parent-child + 1 couple
    assert len(extracted) == 3
    parent_child_rels = [r for r in extracted if r["rel_type"] == "parent-child"]
    couple_rels = [r for r in extracted if r["rel_type"] == "couple"]
    assert len(parent_child_rels) == 2
    assert len(couple_rels) == 1


class MockFamilySearchClient:
    """Mock client returning 2-generation ancestry payload."""

    def get_ancestry(self, pid: str, **kwargs):
        return {
            "persons": [
                {
                    "id": pid,
                    "display": {
                        "name": "Root Person",
                        "gender": "Male",
                        "ascendancyNumber": "1",
                    },
                },
                {
                    "id": "P_FATHER",
                    "display": {
                        "name": "Father Person",
                        "gender": "Male",
                        "ascendancyNumber": "2",
                    },
                },
                {
                    "id": "P_MOTHER",
                    "display": {
                        "name": "Mother Person",
                        "gender": "Female",
                        "ascendancyNumber": "3",
                    },
                },
            ],
            "childAndParentsRelationships": [
                {
                    "id": "rel_01",
                    "child": {"resourceId": pid},
                    "father": {"resourceId": "P_FATHER"},
                    "mother": {"resourceId": "P_MOTHER"},
                }
            ],
        }


def test_derive_pedigree_parent_child_relationships():
    asc_map = {1: "CHILD", 2: "FATHER", 3: "MOTHER", 4: "PAT_GF"}
    derived = derive_pedigree_parent_child_relationships(asc_map)
    # Child -> Father, Child -> Mother, Father -> Pat_GF
    assert len(derived) == 3
    child_rels = [r for r in derived if r["child_pid"] == "CHILD"]
    assert len(child_rels) == 2
    father_rel = [r for r in derived if r["child_pid"] == "FATHER"]
    assert len(father_rel) == 1
    assert father_rel[0]["parent_pid"] == "PAT_GF"


def test_pedigree_ingester():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ingest_test.sqlite"
        db = Database(db_path)
        client = MockFamilySearchClient()
        ingester = PedigreeIngester(client, db)

        result = ingester.ingest_ancestry("ROOT_01", max_generations=2)
        assert result.total_persons == 3
        assert result.total_relationships >= 3
        assert result.status == "completed"

        # Check DB contents
        stats = db.get_pedigree_stats("ROOT_01")
        assert stats["total_ancestors"] == 3
        assert stats["generations"][0]["count"] == 1
        assert stats["generations"][1]["count"] == 2


def test_calculate_global_ahnentafel():
    # Frontier ancestor = Ahnentafel 16 (father.father.father.father)
    gen, asc, path = calculate_global_ahnentafel(16, 1)
    assert gen == 4
    assert asc == 16
    assert path == "father.father.father.father"

    # Sub-ancestor 2 = father of Ahnentafel 16 (Ahnentafel 32, Gen 5)
    gen, asc, path = calculate_global_ahnentafel(16, 2)
    assert gen == 5
    assert asc == 32
    assert path == "father.father.father.father.father"

    # Sub-ancestor 3 = mother of Ahnentafel 16 (Ahnentafel 33, Gen 5)
    gen, asc, path = calculate_global_ahnentafel(16, 3)
    assert gen == 5
    assert asc == 33
    assert path == "father.father.father.father.mother"

    # Deep sub-ancestor: Gen 7 frontier (136), relative gen 3 (sub_asc = 8) -> Gen 10 (asc = 1088)
    gen, asc, path = calculate_global_ahnentafel(136, 8)
    assert gen == 10
    assert asc == 1088
    assert path.endswith(".father.father.father")

    # Ultra-deep sub-ancestor: Gen 10 frontier (1024), relative gen 5 (sub_asc = 32) -> Gen 15 (asc = 32768)
    gen, asc, path = calculate_global_ahnentafel(1024, 32)
    assert gen == 15
    assert asc == 32768


def test_recursive_frontier_expansion():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_recursive.sqlite"
        db = Database(db_path)

        class MultiTierMockClient:
            def get_ancestry(self, pid: str, generations: int = 1, **kwargs):
                if pid == "ROOT":
                    return {
                        "persons": [
                            {"id": "ROOT", "display": {"name": "Root", "ascendancyNumber": "1"}},
                            {"id": "F1", "display": {"name": "Father", "ascendancyNumber": "2"}},
                        ],
                        "relationships": [],
                    }
                elif pid == "F1":
                    return {
                        "persons": [
                            {"id": "F1", "display": {"name": "Father", "ascendancyNumber": "1"}},
                            {"id": "GF2", "display": {"name": "Grandfather", "ascendancyNumber": "2"}},
                        ],
                        "relationships": [],
                    }
                elif pid == "GF2":
                    return {
                        "persons": [
                            {"id": "GF2", "display": {"name": "Grandfather", "ascendancyNumber": "1"}},
                            {"id": "GGF3", "display": {"name": "Great-Grandfather", "ascendancyNumber": "2"}},
                        ],
                        "relationships": [],
                    }
                return {"persons": [], "relationships": []}

        client = MultiTierMockClient()
        ingester = PedigreeIngester(client, db)

        # Ingest base 1, recursive to 3
        res = ingester.ingest_ancestry("ROOT", max_generations=1, recursive_to=3)
        assert res.status == "completed"
        stats = db.get_pedigree_stats("ROOT")
        # Should have ROOT (gen 0), F1 (gen 1), GF2 (gen 2), GGF3 (gen 3)
        assert stats["total_ancestors"] == 4
        assert 0 in stats["generations"]
        assert 1 in stats["generations"]
        assert 2 in stats["generations"]
        assert 3 in stats["generations"]


