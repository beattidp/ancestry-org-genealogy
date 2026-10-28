"""Base models and scoring algorithms for multi-source external record harvesters."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.constraints.date_parser import parse_date


@dataclass
class CandidateDiscovery:
    """Represents a discovered candidate external record for an ancestor."""

    person_pid: str
    harvester: str
    discovery_type: str
    title: str
    date_str: str | None
    url: str | None
    source_identifier: str | None
    snippet_text: str | None
    confidence_score: float = 0.0
    relevance_reason: str | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        """Serializes candidate discovery to dictionary for database persistence."""
        return {
            "person_pid": self.person_pid,
            "harvester": self.harvester,
            "discovery_type": self.discovery_type,
            "title": self.title,
            "date_str": self.date_str,
            "url": self.url,
            "source_identifier": self.source_identifier,
            "snippet_text": self.snippet_text,
            "confidence_score": round(self.confidence_score, 3),
            "relevance_reason": self.relevance_reason,
            "raw_json": self.raw_json,
            "status": self.status,
        }


def extract_year(date_str: str | None) -> int | None:
    """Extracts a 4-digit year from an arbitrary date string."""
    if not date_str:
        return None
    d = parse_date(date_original=str(date_str))
    if d and d.year:
        return d.year
    m = re.search(r"\b(1[4-9]\d{2}|20\d{2})\b", str(date_str))
    return int(m.group(1)) if m else None


def extract_person_lifespan_years(person: dict[str, Any]) -> tuple[int | None, int | None]:
    """Extracts (birth_year, death_year) from person dictionary."""
    b_year = extract_year(person.get("birth_date"))
    d_year = extract_year(person.get("death_date"))

    if (b_year is None or d_year is None) and person.get("lifespan"):
        parts = person["lifespan"].split("-")
        if len(parts) >= 1 and b_year is None:
            b_year = extract_year(parts[0])
        if len(parts) >= 2 and d_year is None:
            d_year = extract_year(parts[1])

    return b_year, d_year


def score_candidate(
    person: dict[str, Any],
    title: str,
    date_str: str | None,
    snippet: str | None,
    location_str: str | None = None,
    facts: list[dict[str, Any]] | None = None,
) -> tuple[float, str, str]:
    """Calculates confidence score, relevance reason, and refined discovery type.

    Returns:
        (confidence_score, relevance_reason, discovery_type)
    """
    score = 0.0
    reasons: list[str] = []
    discovery_type = "record_mention"

    text_to_search = f"{title} {snippet or ''}".lower()
    person_name = (person.get("name") or "").strip()
    name_parts = person_name.split()

    first_name = name_parts[0].lower() if name_parts else ""
    surname = name_parts[-1].lower() if len(name_parts) > 1 else ""

    # 1. Name Match Scoring
    if person_name.lower() in text_to_search:
        score += 0.40
        reasons.append(f'Exact name match ("{person_name}")')
    elif first_name and surname and (first_name in text_to_search and surname in text_to_search):
        score += 0.30
        reasons.append(f'Given name + surname match ("{first_name} {surname}")')
    elif first_name and surname and f"{first_name[0]}. {surname}" in text_to_search:
        score += 0.25
        reasons.append(f'Initial + surname match ("{first_name[0].upper()}. {surname.title()}")')
    elif surname and surname in text_to_search:
        score += 0.10
        reasons.append(f'Surname match ("{surname.title()}")')

    # 2. Lifespan & Date Correlation
    doc_year = extract_year(date_str)
    b_year, d_year = extract_person_lifespan_years(person)

    if doc_year:
        if b_year and d_year:
            if (b_year - 5) <= doc_year <= (d_year + 2):
                score += 0.30
                reasons.append(f"In-lifespan date ({doc_year} within {b_year}–{d_year})")
            elif d_year < doc_year <= (d_year + 50):
                score += 0.15
                reasons.append(f"Post-mortem memorial/probate window ({doc_year})")
            elif doc_year < (b_year - 20) or doc_year > (d_year + 100):
                score -= 0.30
                reasons.append(f"Date out of range ({doc_year} outside {b_year}–{d_year})")
        elif b_year and (b_year - 5) <= doc_year <= (b_year + 90):
            score += 0.20
            reasons.append(f"Compatible with birth year ({b_year})")
        elif d_year and (d_year - 90) <= doc_year <= (d_year + 2):
            score += 0.20
            reasons.append(f"Compatible with death year ({d_year})")

    # 3. Geographic / Location Correlation
    known_places: set[str] = set()
    for place_field in ("birth_place", "death_place"):
        val = person.get(place_field)
        if val:
            for token in re.split(r"[,/]+", val.lower()):
                token = token.strip()
                if len(token) > 3 and token not in {"united states", "county"}:
                    known_places.add(token)

    if facts:
        for f in facts:
            for p_key in ("place_original", "place_normalized"):
                val = f.get(p_key)
                if val:
                    for token in re.split(r"[,/]+", val.lower()):
                        token = token.strip()
                        if len(token) > 3 and token not in {"united states", "county"}:
                            known_places.add(token)

    matched_places = [p for p in known_places if p in text_to_search or (location_str and p in location_str.lower())]
    if matched_places:
        score += 0.25
        reasons.append(f"Geographic match ({', '.join(p.title() for p in matched_places[:2])})")

    # 4. Maritime & Immigration Keywords
    maritime_keywords = [
        "arrived", "arrival", "passengers", "passenger", "manifest",
        "steamer", "steamship", "vessel", "bark", "brig", "schooner",
        "port of", "immigrant", "emigrant", "voyage"
    ]
    matched_maritime = [kw for kw in maritime_keywords if kw in text_to_search]
    if matched_maritime:
        score += 0.15
        discovery_type = "maritime_arrival"
        reasons.append(f"Maritime/passenger terms ({', '.join(matched_maritime[:2])})")

    # 5. Obituary & Probate Keywords
    obit_keywords = ["died", "funeral", "obituary", "native of", "probate", "estate of", "last will"]
    matched_obit = [kw for kw in obit_keywords if kw in text_to_search]
    if matched_obit and discovery_type != "maritime_arrival":
        score += 0.10
        discovery_type = "obituary_or_probate"
        reasons.append(f"Vital/probate terms ({', '.join(matched_obit[:2])})")

    # Clamp score to [0.0, 1.0]
    final_score = max(0.0, min(1.0, score))
    relevance_reason = "; ".join(reasons) if reasons else "Keyword match"

    return final_score, relevance_reason, discovery_type


class BaseHarvester(ABC):
    """Abstract base class for external record harvesters."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def search_person(
        self,
        person: dict[str, Any],
        facts: list[dict[str, Any]] | None = None,
        limit: int = 10,
    ) -> list[CandidateDiscovery]:
        """Searches external repository for candidates matching person and known facts."""
        pass
