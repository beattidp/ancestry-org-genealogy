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


def test_audit_pedigree_incremental_and_scoping():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit_incremental.sqlite"
        db = Database(db_path)

        calls = []

        class TrackingClient(MockFamilySearchClient):
            def get_person_sources(self, pid: str):
                calls.append(pid)
                return super().get_person_sources(pid)

        client = TrackingClient()
        auditor = SourceAuditor(client, db)

        # Setup pedigree: P0 (gen 0), P1 (gen 1), P2 (gen 2)
        p0 = {"pid": "P0", "name": "Person 0", "gender": "Male"}
        p1 = {"pid": "P1", "name": "Person 1", "gender": "Male"}
        p2 = {"pid": "P2", "name": "Person 2", "gender": "Male"}
        db.upsert_persons_batch([p0, p1, p2])
        db.upsert_pedigree_node("P0", "P0", 0, 1, "self")
        db.upsert_pedigree_node("P0", "P1", 1, 2, "father")
        db.upsert_pedigree_node("P0", "P2", 2, 4, "father.father")

        # Pre-seed sources for P0
        db.upsert_sources_batch([{"id": "SRC_P0", "title": "Birth Cert", "tier": 1, "record_type": "vital_birth"}])
        db.upsert_person_sources_batch([{"id": "ps_p0", "person_pid": "P0", "source_id": "SRC_P0"}])
        assert db.has_person_sources("P0")
        assert not db.has_person_sources("P1")

        # Test max_generation=1 scoping: P2 should not be audited or fetched
        assessments = auditor.audit_pedigree("P0", fetch=True, only_missing=True, refresh=False, max_generation=1)
        assert len(assessments) == 2
        pids = [a.person_pid for a in assessments]
        assert "P0" in pids and "P1" in pids
        assert "P2" not in pids

        # P0 was already cached, so only P1 was fetched
        assert "P0" not in calls
        assert "P1" in calls

        # Verify db.get_audit_summary respects max_generation
        summary_gen1 = db.get_audit_summary("P0", max_generation=1)
        assert summary_gen1["total_ancestors"] == 2
        assert 2 not in summary_gen1["generations"]


def test_source_classifier_deep_historical_records():
    # Heralds' Visitations
    src_visitation = {"title": "The Visitation of the County of Worcester, 1569"}
    tier, rtype = classify_source(src_visitation)
    assert tier == 2
    assert rtype == "heraldic_visitation"

    # Parish Register
    src_parish = {"title": "Parish Register of St Mary, Bury St Edmunds, 1538-1600"}
    tier, rtype = classify_source(src_parish)
    assert tier == 1
    assert rtype == "parish_register"

    # Inquisition Post Mortem
    src_ipm = {"title": "Inquisition Post Mortem of Sir Thomas Neville, 1546"}
    tier, rtype = classify_source(src_ipm)
    assert tier == 1
    assert rtype == "probate"

    # Peerage Compilation
    src_peerage = {"title": "The Complete Peerage of England, Scotland, Ireland"}
    tier, rtype = classify_source(src_peerage)
    assert tier == 2
    assert rtype == "peerage"

    # Alumni Register
    src_alumni = {"title": "Alumni Oxonienses: The Members of the University of Oxford, 1500-1714"}
    tier, rtype = classify_source(src_alumni)
    assert tier == 2
    assert rtype == "secondary"


def test_audit_pedigree_min_generation_scoping():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_min_gen.sqlite"
        db = Database(db_path)
        client = MockFamilySearchClient()
        auditor = SourceAuditor(client, db)

        # Setup pedigree with Gen 0..3
        for g in range(4):
            pid = f"P{g}"
            db.upsert_person({"pid": pid, "name": f"Person Gen {g}", "gender": "Male"})
            db.upsert_pedigree_node("P0", pid, g, 2**g if g > 0 else 1, "lineage")

        # Scope audit to Gen 2..3
        assessments = auditor.audit_pedigree("P0", min_generation=2, max_generation=3)
        assert len(assessments) == 2
        pids = [a.person_pid for a in assessments]
        assert "P2" in pids and "P3" in pids
        assert "P0" not in pids and "P1" not in pids

        # Summary scoped to Gen 2..3
        summary = db.get_audit_summary("P0", min_generation=2, max_generation=3)
        assert summary["total_ancestors"] == 2
        assert set(summary["generations"].keys()) == {2, 3}

