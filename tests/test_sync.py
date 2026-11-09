"""Unit tests for FamilySearch Targeted Synchronization Engine."""

from pathlib import Path
import sqlite3
import pytest
from unittest.mock import MagicMock

from src.familysearch.sync import (
    SyncEngine,
    SyncActionType,
    DiscoverySyncRecord,
    SyncReport,
)
from src.familysearch.client import FamilySearchClient, FamilySearchAuthError


@pytest.fixture
def mock_sqlite_db(tmp_path: Path) -> Path:
    """Creates a temporary SQLite database with candidate discoveries and facts."""
    db_file = tmp_path / "test_pedigree.sqlite"
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE candidate_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_pid TEXT NOT NULL,
                harvester TEXT NOT NULL,
                discovery_type TEXT NOT NULL,
                title TEXT NOT NULL,
                date_str TEXT,
                url TEXT,
                source_identifier TEXT,
                snippet_text TEXT,
                confidence_score REAL DEFAULT 0.0,
                relevance_reason TEXT,
                raw_json TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_pid TEXT,
                fact_type TEXT,
                date_original TEXT,
                date_formal TEXT,
                place_original TEXT,
                place_normalized TEXT,
                value TEXT,
                raw_json TEXT
            )
            """
        )

        # Insert test candidate discoveries
        conn.execute(
            """
            INSERT INTO candidate_discoveries (
                person_pid, harvester, discovery_type, title, date_str, url, confidence_score, relevance_reason, status
            ) VALUES (
                '9ZMG-JSD', 'chronicling_america', 'newspaper_mention',
                'Image 4 of The times (Owosso, Mich.), March 9, 1888',
                '1888-03-09',
                'https://www.loc.gov/resource/sn96077385/1888-03-09/ed-1/?sp=4',
                0.70,
                'Exact name match ("Sample Ancestor")',
                'confirmed'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO candidate_discoveries (
                person_pid, harvester, discovery_type, title, date_str, url, confidence_score, relevance_reason, status
            ) VALUES (
                'KN4P-VCG', 'chronicling_america', 'newspaper_mention',
                'Image 7 of The Anderson news, August 3, 1916',
                '1916-08-03',
                'https://www.loc.gov/resource/sn86069242/1916-08-03/ed-1/?sp=7',
                0.60,
                'Compatible with birth year',
                'pending'
            )
            """
        )

        # Insert test Scottish facts
        conn.execute(
            """
            INSERT INTO facts (person_pid, fact_type, date_original, date_formal, place_original)
            VALUES ('KZDJ-4JK', 'Birth', 'about 1605', '+1605', 'Liberton, Midlothian, Scotland')
            """
        )
        conn.execute(
            """
            INSERT INTO facts (person_pid, fact_type, date_original, date_formal, place_original)
            VALUES ('USA-123', 'Birth', '1850', '+1850', 'Owosso, Shiawassee, Michigan, United States')
            """
        )
        conn.commit()

    return db_file


def test_stage_candidate_discoveries_confirmed(mock_sqlite_db: Path) -> None:
    """Verify only confirmed candidate discoveries are staged by default."""
    engine = SyncEngine(db_path=mock_sqlite_db)
    records = engine.stage_candidate_discoveries(only_confirmed=True)

    assert len(records) == 1
    rec = records[0]
    assert rec.target_pid == "9ZMG-JSD"
    assert rec.action_type == SyncActionType.ATTACH_SOURCE
    assert "Owosso, Mich." in rec.title
    assert "Verified via" in rec.change_message
    assert "Exact name match" in rec.change_message
    assert rec.status == "staged"


def test_stage_candidate_discoveries_with_pending(mock_sqlite_db: Path) -> None:
    """Verify pending candidates meeting min_confidence threshold are staged."""
    engine = SyncEngine(db_path=mock_sqlite_db)
    records = engine.stage_candidate_discoveries(min_confidence=0.55, only_confirmed=False)

    assert len(records) == 2
    pids = [r.target_pid for r in records]
    assert "9ZMG-JSD" in pids
    assert "KN4P-VCG" in pids


def test_stage_scottish_parish_updates(mock_sqlite_db: Path) -> None:
    """Verify Scottish facts resolve to NRS civil parish and attach coordinates."""
    engine = SyncEngine(db_path=mock_sqlite_db)
    records = engine.stage_scottish_parish_updates()

    assert len(records) == 1
    rec = records[0]
    assert rec.target_pid == "KZDJ-4JK"
    assert rec.action_type == SyncActionType.UPDATE_FACT
    assert rec.fact_type == "Birth"
    assert rec.place_str == "Liberton, Midlothian, Scotland"
    assert rec.place_coordinates is not None
    lat, lon = rec.place_coordinates
    assert abs(lat - 55.9142) < 0.001
    assert "NRS Parish #693" in rec.change_message
    assert "places" in rec.gedcomx_payload


def test_execute_sync_dry_run(mock_sqlite_db: Path) -> None:
    """Verify dry-run mode validates payloads without calling client."""
    mock_client = MagicMock(spec=FamilySearchClient)
    engine = SyncEngine(db_path=mock_sqlite_db, client=mock_client)

    staged = engine.stage_candidate_discoveries()
    report = engine.execute_sync(staged, dry_run=True)

    assert report.dry_run is True
    assert report.total_staged == 1
    assert report.total_synced == 1
    assert report.total_failed == 0
    mock_client.add_person_source_citation.assert_not_called()


def test_execute_sync_validation_error() -> None:
    """Verify missing change message causes record failure."""
    engine = SyncEngine()
    invalid_record = DiscoverySyncRecord(
        record_id="invalid:1",
        target_pid="9ZMG-JSD",
        action_type=SyncActionType.ATTACH_SOURCE,
        title="Test",
        change_message="",  # Missing changeMessage
    )

    report = engine.execute_sync([invalid_record], dry_run=True)
    assert report.total_failed == 1
    assert invalid_record.status == "failed"
    assert "Missing changeMessage" in report.errors[0]


def test_execute_sync_live(mock_sqlite_db: Path) -> None:
    """Verify live synchronization calls FamilySearch write endpoints and updates SQLite status."""
    mock_client = MagicMock(spec=FamilySearchClient)
    mock_client.add_person_source_citation.return_value = {}
    mock_client.add_or_update_person_fact.return_value = {}

    engine = SyncEngine(db_path=mock_sqlite_db, client=mock_client)

    staged_sources = engine.stage_candidate_discoveries()
    staged_facts = engine.stage_scottish_parish_updates()

    all_staged = staged_sources + staged_facts
    report = engine.execute_sync(all_staged, dry_run=False)

    assert report.dry_run is False
    assert report.total_synced == 2
    assert report.total_failed == 0

    mock_client.add_person_source_citation.assert_called_once()
    mock_client.add_or_update_person_fact.assert_called_once()

    # Verify status in SQLite database updated to 'synced'
    with sqlite3.connect(mock_sqlite_db) as conn:
        row = conn.execute("SELECT status FROM candidate_discoveries WHERE id = 1").fetchone()
        assert row[0] == "synced"


def test_format_summary_table() -> None:
    """Verify report formatting outputs valid markdown summary."""
    rec = DiscoverySyncRecord(
        record_id="candidate_discovery:1",
        target_pid="9ZMG-JSD",
        action_type=SyncActionType.ATTACH_SOURCE,
        title="1888 Owosso Times",
        change_message="Verified via 1888 Owosso Times",
        status="synced",
    )
    report = SyncReport(
        total_staged=1,
        total_synced=1,
        dry_run=True,
        records=[rec],
    )
    table = SyncEngine.format_summary_table(report)
    assert "DRY-RUN" in table
    assert "9ZMG-JSD" in table
    assert "1888 Owosso Times" in table
