"""Unit tests for SourceClassifier and SourceAuditor."""

import tempfile
from pathlib import Path
import pytest

from src.audit.classifier import SourceClassifier, classify_source
from src.audit.auditor import SourceAuditor
from src.storage.db import Database


def test_source_classifier_tier1_census():
    src = {
        "title": "United States Census, 1920",
        "citation_text": "1920 Census, Los Angeles, California",
        "about_url": "https://familysearch.org/ark:/61903/1:1:MH7M-123",
    }
    tier, rtype = classify_source(src)
    assert tier == 1
    assert rtype == "census"


def test_source_classifier_tier1_vitals():
    src_birth = {"title": "California, Birth Index, 1905-1995"}
    assert classify_source(src_birth) == (1, "vital_birth")

    src_death = {"title": "California, Death Certificate, 1940-1997"}
    assert classify_source(src_death) == (1, "vital_death")

    src_marriage = {"title": "Washington County Marriage Records, 1880-1920"}
    assert classify_source(src_marriage) == (1, "vital_marriage")

    src_cemetery = {"title": "Find A Grave Index"}
    assert classify_source(src_cemetery) == (1, "vital_death")


def test_source_classifier_tier1_military_and_ssn():
    src_draft = {"title": "World War II Draft Registration Cards, 1940-1947"}
    assert classify_source(src_draft) == (1, "military")

    src_numident = {"title": "United States, Social Security Numerical Identification Files (NUMIDENT)"}
    assert classify_source(src_numident) == (1, "social_security")


def test_source_classifier_tier2_secondary():
    src_obit = {"title": "The Los Angeles Times Obituary, 1955"}
    tier, rtype = classify_source(src_obit)
    assert tier == 2
    assert rtype == "secondary"


def test_source_classifier_tier3_user_tree():
    src_prf = {"title": "Pedigree Resource File, user submission"}
    tier, rtype = classify_source(src_prf)
    assert tier == 3
    assert rtype == "user_tree"

    src_ancestry = {"title": "Ancestry Family Tree - John Smith Family"}
    tier, rtype = classify_source(src_ancestry)
    assert tier == 3
    assert rtype == "user_tree"


class MockFamilySearchClient:
    """Mock client returning source descriptions."""

    def get_person_sources(self, pid: str):
        if pid == "P_WELL_SOURCED":
            return {
                "sourceDescriptions": [
                    {
                        "id": "SD01",
                        "titles": [{"value": "United States Census, 1920"}],
                        "about": "https://familysearch.org/ark:/61903/1:1:123",
                        "citations": [{"value": "1920 census"}],
                    },
                    {
                        "id": "SD02",
                        "titles": [{"value": "California Death Certificate"}],
                        "about": "https://familysearch.org/ark:/61903/1:1:456",
                        "citations": [{"value": "Death certificate"}],
                    },
                ],
                "persons": [
                    {
                        "id": pid,
                        "sources": [
                            {"id": "c1", "descriptionId": "SD01", "tags": [{"resource": "http://gedcomx.org/Birth"}]},
                            {"id": "c2", "descriptionId": "SD02", "tags": [{"resource": "http://gedcomx.org/Death"}]},
                        ],
                    }
                ],
            }
        return {"sourceDescriptions": [], "persons": []}


def test_source_auditor_scoring():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.sqlite"
        db = Database(db_path)
        client = MockFamilySearchClient()
        auditor = SourceAuditor(client, db)

        # Setup person and parent
        p1 = {"pid": "P_WELL_SOURCED", "name": "Well Sourced", "gender": "Male", "living": False}
        p_parent = {"pid": "P_PARENT", "name": "Parent", "gender": "Male"}
        db.upsert_persons_batch([p1, p_parent])
        db.upsert_relationship(
            {"id": "rel_pc", "rel_type": "parent-child", "parent_pid": "P_PARENT", "child_pid": "P_WELL_SOURCED"}
        )

        # Fetch and store sources
        stored_count = auditor.fetch_and_store_person_sources("P_WELL_SOURCED")
        assert stored_count == 2

        # Audit person
        assessment = auditor.audit_person("P_WELL_SOURCED")
        assert assessment.birth_verified
        assert assessment.death_verified
        assert assessment.parentage_verified
        assert assessment.confidence_level == "HIGH"
        assert assessment.confidence_score >= 80.0


def test_source_auditor_unsourced():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit_unsourced.sqlite"
        db = Database(db_path)
        client = MockFamilySearchClient()
        auditor = SourceAuditor(client, db)

        p = {"pid": "P_EMPTY", "name": "Empty Person", "gender": "Female"}
        db.upsert_person(p)

        assessment = auditor.audit_person("P_EMPTY")
        assert assessment.total_sources == 0
        assert assessment.confidence_level == "UNSOURCED"
        assert assessment.confidence_score == 0.0
