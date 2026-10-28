"""Internet Archive digitized passenger list, county history, and monograph harvester."""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from src.sources.base import (
    BaseHarvester,
    CandidateDiscovery,
    score_candidate,
)

logger = logging.getLogger(__name__)


class InternetArchiveHarvester(BaseHarvester):
    """Harvester for Internet Archive digitized texts, passenger lists, and family genealogies."""

    BASE_URL = "https://archive.org/advancedsearch.php"
    USER_AGENT = "AncestryGenealogyBot/1.0 (+https://github.com/beattidp/ancestry-genealogy)"

    def __init__(self, timeout: int = 30) -> None:
        super().__init__(name="internet_archive")
        self.timeout = timeout

    def _fetch_ia_json(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Executes search query against the Internet Archive Advanced Search API."""
        params = [
            ("q", query),
            ("fl[]", "identifier"),
            ("fl[]", "title"),
            ("fl[]", "creator"),
            ("fl[]", "date"),
            ("fl[]", "year"),
            ("fl[]", "description"),
            ("fl[]", "mediatype"),
            ("rows", str(limit)),
            ("output", "json"),
        ]
        query_string = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}?{query_string}"
        req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content = response.read().decode("utf-8")
                data = json.loads(content)
                return data.get("response", {}).get("docs", [])
        except Exception as e:
            logger.warning("Error querying Internet Archive API (%s): %s", url, e)
            return []

    def search_person(
        self,
        person: dict[str, Any],
        facts: list[dict[str, Any]] | None = None,
        limit: int = 10,
    ) -> list[CandidateDiscovery]:
        """Searches Internet Archive for passenger list compendiums and family genealogies."""
        person_name = (person.get("name") or "").strip()
        if not person_name:
            return []

        name_parts = person_name.split()
        surname = name_parts[-1] if len(name_parts) > 1 else person_name

        candidates: list[CandidateDiscovery] = []
        seen_identifiers: set[str] = set()

        # 1. Family Monograph & Genealogy Query
        monograph_query = (
            f'mediatype:texts AND (title:("{surname} family" OR "{surname} genealogy" OR "{surname} history") '
            f'OR description:("{person_name}"))'
        )
        docs = self._fetch_ia_json(monograph_query, limit=limit)
        for doc in docs:
            disc = self._parse_ia_doc(person, doc, facts, default_type="monograph")
            if disc and disc.source_identifier not in seen_identifiers:
                seen_identifiers.add(disc.source_identifier)
                candidates.append(disc)

        # 2. Passenger Lists & Immigrant Compendiums Query
        if len(candidates) < limit:
            passenger_query = (
                f'mediatype:texts AND ("passenger list" OR "ship passenger" OR "immigrants" OR "emigrants") '
                f'AND "{surname}"'
            )
            p_docs = self._fetch_ia_json(passenger_query, limit=min(5, limit - len(candidates)))
            for doc in p_docs:
                disc = self._parse_ia_doc(person, doc, facts, default_type="passenger_list")
                if disc and disc.source_identifier not in seen_identifiers:
                    seen_identifiers.add(disc.source_identifier)
                    candidates.append(disc)

        # 3. County / Regional History Query (if state/county is known)
        place = person.get("birth_place") or person.get("death_place") or ""
        if len(candidates) < limit and place:
            tokens = [t.strip() for t in place.split(",") if len(t.strip()) > 3]
            if tokens:
                region = tokens[0]
                county_query = (
                    f'mediatype:texts AND ("history of {region}" OR "{region} county") AND "{surname}"'
                )
                c_docs = self._fetch_ia_json(county_query, limit=min(5, limit - len(candidates)))
                for doc in c_docs:
                    disc = self._parse_ia_doc(person, doc, facts, default_type="county_history")
                    if disc and disc.source_identifier not in seen_identifiers:
                        seen_identifiers.add(disc.source_identifier)
                        candidates.append(disc)

        # Sort by confidence score descending
        candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        return candidates[:limit]

    def _parse_ia_doc(
        self,
        person: dict[str, Any],
        doc: dict[str, Any],
        facts: list[dict[str, Any]] | None = None,
        default_type: str = "monograph",
    ) -> CandidateDiscovery | None:
        """Parses an Internet Archive document into CandidateDiscovery."""
        identifier = doc.get("identifier")
        if not identifier:
            return None

        title = doc.get("title") or identifier
        if isinstance(title, list):
            title = title[0] if title else identifier

        date_str = str(doc.get("year") or doc.get("date") or "")

        desc = doc.get("description", "")
        if isinstance(desc, list):
            desc_text = " ... ".join(str(d) for d in desc[:2])
        else:
            desc_text = str(desc)

        creator = doc.get("creator", "")
        creator_str = ", ".join(creator) if isinstance(creator, list) else str(creator)

        url = f"https://archive.org/details/{identifier}"

        # Score candidate
        score, reason, disc_type = score_candidate(
            person=person,
            title=title,
            date_str=date_str,
            snippet=f"{desc_text} Creator: {creator_str}",
            facts=facts,
        )

        if disc_type == "record_mention":
            disc_type = default_type

        return CandidateDiscovery(
            person_pid=person["pid"],
            harvester=self.name,
            discovery_type=disc_type,
            title=str(title),
            date_str=date_str if date_str else None,
            url=url,
            source_identifier=identifier,
            snippet_text=desc_text[:1000] if desc_text else None,
            confidence_score=score,
            relevance_reason=reason,
            raw_json={
                "identifier": identifier,
                "title": title,
                "creator": creator_str,
                "date": date_str,
                "mediatype": doc.get("mediatype"),
            },
        )
