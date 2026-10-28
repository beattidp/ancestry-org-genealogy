"""Library of Congress Chronicling America historical newspaper and maritime harvester."""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from src.sources.base import (
    BaseHarvester,
    CandidateDiscovery,
    extract_person_lifespan_years,
    score_candidate,
)

logger = logging.getLogger(__name__)


class ChroniclingAmericaHarvester(BaseHarvester):
    """Harvester for Library of Congress Chronicling America historical newspapers."""

    BASE_URL = "https://www.loc.gov/search/"
    USER_AGENT = "AncestryGenealogyBot/1.0 (+https://github.com/beattidp/ancestry-genealogy)"

    def __init__(self, timeout: int = 35) -> None:
        super().__init__(name="chronicling_america")
        self.timeout = timeout

    def _fetch_loc_json(self, params: dict[str, Any]) -> dict[str, Any]:
        """Executes HTTP GET request against the Library of Congress JSON endpoint."""
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query_string}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read().decode("utf-8")
                return json.loads(content)
        except Exception as e:
            logger.warning("Error querying Library of Congress API (%s): %s", url, e)
            return {}

    def search_person(
        self,
        person: dict[str, Any],
        facts: list[dict[str, Any]] | None = None,
        limit: int = 10,
        include_maritime: bool = True,
    ) -> list[CandidateDiscovery]:
        """Searches historical newspapers for person name, obituary, and maritime port arrivals."""
        person_name = (person.get("name") or "").strip()
        if not person_name:
            return []

        b_year, d_year = extract_person_lifespan_years(person)
        start_year = b_year if b_year else 1800
        end_year = (d_year + 5) if d_year else min(start_year + 90, 1963)

        # Cap within chronicling america range
        start_year = max(1777, min(start_year, 1963))
        end_year = max(start_year, min(end_year, 1963))

        candidates: list[CandidateDiscovery] = []
        seen_urls: set[str] = set()

        # 1. Primary Targeted Query: Full Name in quotes
        params: dict[str, Any] = {
            "fo": "json",
            "in": "original-format:newspaper",
            "q": f'"{person_name}"',
            "dates": f"{start_year}/{end_year}",
            "c": limit,
        }

        data = self._fetch_loc_json(params)
        for item in data.get("results", []):
            disc = self._parse_loc_item(person, item, facts)
            if disc and disc.url not in seen_urls:
                seen_urls.add(disc.url)
                candidates.append(disc)

        # 2. Maritime Arrival Query (if requested and surname available)
        name_parts = person_name.split()
        surname = name_parts[-1] if len(name_parts) > 1 else ""
        if include_maritime and surname and len(candidates) < limit:
            # Narrow maritime immigration window: approx age 15 to 40
            m_start = (b_year + 15) if b_year else start_year
            m_end = (b_year + 45) if b_year else min(start_year + 45, end_year)
            m_start = max(1777, min(m_start, 1963))
            m_end = max(m_start, min(m_end, 1963))

            maritime_query = f'"{surname}" AND (ship OR arrival OR passengers OR steamer OR bark)'
            maritime_params: dict[str, Any] = {
                "fo": "json",
                "in": "original-format:newspaper",
                "q": maritime_query,
                "dates": f"{m_start}/{m_end}",
                "c": min(5, limit - len(candidates)),
            }

            m_data = self._fetch_loc_json(maritime_params)
            for item in m_data.get("results", []):
                disc = self._parse_loc_item(person, item, facts, default_type="maritime_arrival")
                if disc and disc.url not in seen_urls:
                    seen_urls.add(disc.url)
                    candidates.append(disc)

        # Sort by confidence score descending
        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates[:limit]

    def _parse_loc_item(
        self,
        person: dict[str, Any],
        item: dict[str, Any],
        facts: list[dict[str, Any]] | None = None,
        default_type: str = "newspaper_mention",
    ) -> CandidateDiscovery | None:
        """Parses a Library of Congress API result item into CandidateDiscovery."""
        url = item.get("url")
        if not url:
            return None

        title = item.get("title") or "Historical Newspaper Article"
        date_str = item.get("date")

        # Location details
        loc_list = item.get("location", [])
        location_str = ", ".join(loc_list) if isinstance(loc_list, list) else str(loc_list)

        # Snippet extraction
        snippets = item.get("description", [])
        snippet_text = ""
        if isinstance(snippets, list) and snippets:
            snippet_text = " ... ".join(str(s) for s in snippets[:3])
        elif isinstance(snippets, str):
            snippet_text = snippets

        # Score candidate
        score, reason, disc_type = score_candidate(
            person=person,
            title=title,
            date_str=date_str,
            snippet=snippet_text,
            location_str=location_str,
            facts=facts,
        )

        if disc_type == "record_mention":
            disc_type = default_type

        return CandidateDiscovery(
            person_pid=person["pid"],
            harvester=self.name,
            discovery_type=disc_type,
            title=title,
            date_str=date_str,
            url=url,
            source_identifier=item.get("id"),
            snippet_text=snippet_text[:1000] if snippet_text else None,
            confidence_score=score,
            relevance_reason=reason,
            raw_json={
                "id": item.get("id"),
                "title": title,
                "date": date_str,
                "url": url,
                "location": loc_list,
            },
        )
