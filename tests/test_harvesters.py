"""Unit tests for external record harvesters and candidate discovery engine."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.sources.base import (
    CandidateDiscovery,
    extract_person_lifespan_years,
    extract_year,
    score_candidate,
)
from src.sources.chronicling_america import ChroniclingAmericaHarvester
from src.sources.internet_archive import InternetArchiveHarvester
from src.storage.db import Database


@pytest.fixture
def temp_db(tmp_path: Any) -> Database:
    """Fixture providing a clean SQLite database instance."""
    db_file = tmp_path / "test_pedigree.sqlite"
    return Database(db_path=db_file)


# -------------------------------------------------------------------------
# 1. Scoring & Base Helper Tests
# -------------------------------------------------------------------------


def test_extract_year() -> None:
    assert extract_year("1828") == 1828
    assert extract_year("about 1828") == 1828
    assert extract_year("21 Jan 1908") == 1908
    assert extract_year("+1908-01-21") == 1908
    assert extract_year("invalid") is None
    assert extract_year(None) is None


def test_extract_person_lifespan_years() -> None:
    p1 = {"birth_date": "about 1828", "death_date": "19 Jan 1908", "lifespan": "1828-1908"}
    assert extract_person_lifespan_years(p1) == (1828, 1908)

    p2 = {"lifespan": "1850-1920"}
    assert extract_person_lifespan_years(p2) == (1850, 1920)

    p3 = {"birth_date": "1880", "death_date": None, "lifespan": "1880-Living"}
    assert extract_person_lifespan_years(p3) == (1880, None)


def test_score_candidate_exact_match_and_maritime() -> None:
    person = {
        "name": "Adam Beattie",
        "birth_date": "1828",
        "death_date": "1908",
        "birth_place": "Ireland",
        "death_place": "Redwood, Sonoma, California",
    }
    title = "Steamer Arrival: Passengers from Liverpool"
    snippet = "Among the passengers on the vessel was Adam Beattie, native of Ireland."
    date_str = "1855-06-12"

    score, reason, disc_type = score_candidate(
        person=person,
        title=title,
        date_str=date_str,
        snippet=snippet,
    )

    assert disc_type == "maritime_arrival"
    assert score >= 0.70
    assert 'Exact name match ("Adam Beattie")' in reason
    assert "In-lifespan date" in reason
    assert "Geographic match (Ireland)" in reason
    assert "Maritime/passenger terms" in reason


def test_score_candidate_obituary_match() -> None:
    person = {
        "name": "Adam Beattie",
        "birth_date": "1828",
        "death_date": "19 Jan 1908",
        "death_place": "Sonoma, California",
    }
    title = "Funeral of Adam Beattie Held in Sonoma"
    snippet = "Adam Beattie died on Sunday at his home in Redwood. Funeral services were conducted."
    date_str = "1908-01-22"

    score, reason, disc_type = score_candidate(
        person=person,
        title=title,
        date_str=date_str,
        snippet=snippet,
    )

    assert disc_type == "obituary_or_probate"
    assert score >= 0.80
    assert "Vital/probate terms" in reason
    assert "Geographic match (Sonoma)" in reason


def test_score_candidate_out_of_range_penalty() -> None:
    person = {
        "name": "Adam Beattie",
        "birth_date": "1828",
        "death_date": "1908",
    }
    title = "High School Basketball Tournament"
    snippet = "Coach Adam Beattie led the team to victory."
    date_str = "2024-03-15"

    score, reason, disc_type = score_candidate(
        person=person,
        title=title,
        date_str=date_str,
        snippet=snippet,
    )

    assert "Date out of range" in reason
    assert score < 0.30


# -------------------------------------------------------------------------
# 2. Chronicling America Harvester Tests
# -------------------------------------------------------------------------


@patch.object(ChroniclingAmericaHarvester, "_fetch_loc_json")
def test_chronicling_america_search_person(mock_fetch: MagicMock) -> None:
    mock_fetch.return_value = {
        "results": [
            {
                "id": "item1",
                "title": "Image 1 of Daily News (San Francisco, Cal.)",
                "date": "1875-04-10",
                "url": "https://www.loc.gov/resource/item1",
                "location": ["california", "san francisco"],
                "description": ["Adam Beattie arrived on the steamer from Panama."],
            }
        ]
    }

    harvester = ChroniclingAmericaHarvester()
    person = {
        "pid": "P-101",
        "name": "Adam Beattie",
        "birth_date": "1828",
        "death_date": "1908",
        "death_place": "Sonoma, California",
    }

    results = harvester.search_person(person, limit=5, include_maritime=False)

    assert len(results) == 1
    disc = results[0]
    assert disc.person_pid == "P-101"
    assert disc.harvester == "chronicling_america"
    assert disc.discovery_type == "maritime_arrival"
    assert disc.date_str == "1875-04-10"
    assert disc.url == "https://www.loc.gov/resource/item1"
    assert disc.confidence_score >= 0.70


# -------------------------------------------------------------------------
# 3. Internet Archive Harvester Tests
# -------------------------------------------------------------------------


@patch.object(InternetArchiveHarvester, "_fetch_ia_json")
def test_internet_archive_search_person(mock_fetch: MagicMock) -> None:
    mock_fetch.side_effect = [
        # Call 1: Monograph query
        [
            {
                "identifier": "beattiefamily001",
                "title": "Genealogy of the Beattie Family in America",
                "date": "1915",
                "creator": ["Beattie, James"],
                "description": "Comprehensive history of Adam Beattie and descendants in California.",
                "mediatype": "texts",
            }
        ],
        # Call 2: Passenger list query
        [
            {
                "identifier": "passengerlists1850",
                "title": "Ship Passenger Lists to California 1849-1860",
                "date": "1920",
                "creator": "Historical Society",
                "description": "Including arrivals for Beattie, Kennedy, and others.",
                "mediatype": "texts",
            }
        ],
        # Call 3: County query (empty)
        [],
    ]

    harvester = InternetArchiveHarvester()
    person = {
        "pid": "P-101",
        "name": "Adam Beattie",
        "birth_date": "1828",
        "death_date": "1908",
        "death_place": "Sonoma, California",
    }

    results = harvester.search_person(person, limit=5)

    assert len(results) == 2
    assert results[0].source_identifier == "beattiefamily001"
    assert results[0].url == "https://archive.org/details/beattiefamily001"
    assert results[0].confidence_score >= 0.50
    assert results[1].source_identifier == "passengerlists1850"


# -------------------------------------------------------------------------
# 4. Storage & Persistence Tests
# -------------------------------------------------------------------------


def test_database_candidate_discoveries(temp_db: Database) -> None:
    person = {
        "pid": "P-101",
        "name": "Adam Beattie",
        "gender": "Male",
        "lifespan": "1828-1908",
        "living": 0,
    }
    temp_db.upsert_person(person)

    candidate = {
        "person_pid": "P-101",
        "harvester": "chronicling_america",
        "discovery_type": "maritime_arrival",
        "title": "Steamer Arrival",
        "date_str": "1855-06-12",
        "url": "https://www.loc.gov/resource/test1",
        "source_identifier": "test1",
        "snippet_text": "Adam Beattie arrived on steamer.",
        "confidence_score": 0.85,
        "relevance_reason": "Exact name match + In-lifespan date",
        "status": "pending",
        "raw_json": {"id": "test1"},
    }

    row_id = temp_db.upsert_candidate_discovery(candidate)
    assert row_id is not None

    # Retrieve
    records = temp_db.get_candidate_discoveries(person_pid="P-101", min_confidence=0.5)
    assert len(records) == 1
    assert records[0]["title"] == "Steamer Arrival"
    assert records[0]["confidence_score"] == 0.85
    assert records[0]["person_name"] == "Adam Beattie"

    # Upsert with update to title
    candidate["title"] = "Updated Steamer Arrival"
    candidate["confidence_score"] = 0.90
    temp_db.upsert_candidate_discovery(candidate)

    updated_records = temp_db.get_candidate_discoveries(person_pid="P-101")
    assert len(updated_records) == 1
    assert updated_records[0]["title"] == "Updated Steamer Arrival"
    assert updated_records[0]["confidence_score"] == 0.90

    # Summary
    summary = temp_db.get_discovery_summary()
    assert summary["total_discoveries"] == 1
    assert summary["distinct_persons"] == 1
    assert summary["harvester_counts"] == {"chronicling_america": 1}
    assert summary["average_confidence"] == 0.9
