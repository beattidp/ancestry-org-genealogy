"""Unit tests for pedigree extractor and ingester."""

import tempfile
from pathlib import Path
import pytest
from src.pedigree.extractor import (
    calculate_generation_and_path,
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
