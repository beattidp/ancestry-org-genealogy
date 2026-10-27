"""Source and citation auditing engine for evaluating evidence and scoring pedigree confidence."""

from dataclasses import dataclass, field
from typing import Any, Callable
import time

from src.audit.classifier import classify_source
from src.familysearch.client import FamilySearchClient
from src.storage.db import Database


@dataclass
class AuditAssessment:
    """Evidentiary assessment and confidence score for a single person."""

    person_pid: str
    name: str = ""
    generation: int = 0
    total_sources: int = 0
    tier1_sources: int = 0
    tier2_sources: int = 0
    tier3_sources: int = 0
    birth_verified: bool = False
    death_verified: bool = False
    parentage_verified: bool = False
    confidence_score: float = 0.0
    confidence_level: str = "UNSOURCED"  # HIGH, MEDIUM, LOW, UNSOURCED
    issues: list[str] = field(default_factory=list)


class SourceAuditor:
    """Orchestrates source ingestion, evidence tiering, and pedigree confidence evaluation."""

    def __init__(self, client: FamilySearchClient, db: Database) -> None:
        self.client = client
        self.db = db

    def fetch_and_store_person_sources(self, pid: str) -> int:
        """Fetches attached sources for a person from FamilySearch and saves them locally."""
        try:
            data = self.client.get_person_sources(pid)
        except Exception:
            return 0

        source_descriptions = data.get("sourceDescriptions", [])
        sources_to_save = []
        for sd in source_descriptions:
            sd_id = sd.get("id")
            if not sd_id:
                continue

            titles = sd.get("titles", [])
            title = titles[0].get("value") if titles else ""
            citations = sd.get("citations", [])
            citation_text = citations[0].get("value") if citations else ""
            about_url = sd.get("about") or ""
            identifiers = sd.get("identifiers", {})
            collections = identifiers.get("http://gedcomx.org/Collection", [])
            collection_url = collections[0] if collections else ""

            source_dict = {
                "id": sd_id,
                "title": title,
                "about_url": about_url,
                "citation_text": citation_text,
                "collection_url": collection_url,
                "raw_json": sd,
            }

            tier, record_type = classify_source(source_dict)
            source_dict["tier"] = tier
            source_dict["record_type"] = record_type
            sources_to_save.append(source_dict)

        if sources_to_save:
            self.db.upsert_sources_batch(sources_to_save)

        # Extract citation references linking person to source
        person_sources_to_save = []
        persons = data.get("persons", [])
        if persons:
            person_obj = persons[0]
            sources_refs = person_obj.get("sources", [])
            for sref in sources_refs:
                sref_id = sref.get("id")
                desc_id = sref.get("descriptionId") or sref.get("description", "").lstrip("#")
                if not sref_id or not desc_id:
                    continue

                tags_list = []
                for tag in sref.get("tags", []):
                    res = tag.get("resource", "")
                    clean_tag = res.split("/")[-1] if "/" in res else res
                    if clean_tag:
                        tags_list.append(clean_tag)

                contributor = (
                    sref.get("attribution", {})
                    .get("contributor", {})
                    .get("resourceId")
                )

                person_sources_to_save.append(
                    {
                        "id": sref_id,
                        "person_pid": pid,
                        "source_id": desc_id,
                        "tags": ",".join(tags_list),
                        "contributor": contributor,
                        "raw_json": sref,
                    }
                )

        if person_sources_to_save:
            self.db.upsert_person_sources_batch(person_sources_to_save)

        return len(sources_to_save)

    def audit_person(self, pid: str) -> AuditAssessment:
        """Evaluates evidence coverage and computes confidence score for an individual."""
        person = self.db.get_person(pid)
        person_name = person["name"] if person else "Unknown"

        sources = self.db.get_person_sources(pid)
        total_sources = len(sources)

        tier1_count = sum(1 for s in sources if s["tier"] == 1)
        tier2_count = sum(1 for s in sources if s["tier"] == 2)
        tier3_count = sum(1 for s in sources if s["tier"] == 3)

        issues = []
        birth_verified = False
        death_verified = False
        parentage_verified = False

        # 1. Birth verification check
        # Look for Tier 1 source with Birth in tags or vital_birth / social_security / census
        for s in sources:
            tags = (s.get("tags") or "").split(",")
            rtype = s.get("record_type", "")
            if s["tier"] == 1:
                if "Birth" in tags or rtype in ("vital_birth", "social_security", "census"):
                    birth_verified = True
                    break

        if not birth_verified and person and not person.get("living"):
            issues.append("Missing Tier 1 primary birth or census record")

        # 2. Death verification check
        # Look for Tier 1 source with Death in tags or vital_death / social_security
        for s in sources:
            tags = (s.get("tags") or "").split(",")
            rtype = s.get("record_type", "")
            if s["tier"] == 1:
                if "Death" in tags or rtype in ("vital_death", "social_security"):
                    death_verified = True
                    break

        if not death_verified and person and not person.get("living"):
            issues.append("Missing Tier 1 primary death or cemetery record")

        # 3. Parentage verification check
        # Check if person has parents in the database
        with self.db.get_connection() as conn:
            parent_rels = conn.execute(
                "SELECT parent_pid FROM relationships WHERE child_pid = ? AND rel_type = 'parent-child'",
                (pid,),
            ).fetchall()

        has_parents = len(parent_rels) > 0
        if not has_parents:
            issues.append("Parentage unlinked in pedigree (brick wall)")
        else:
            # Does a Tier 1 or Tier 2 documentary record corroborate family household (Census, birth register)?
            for s in sources:
                rtype = s.get("record_type", "")
                if s["tier"] in (1, 2) and rtype in ("census", "vital_birth", "probate"):
                    parentage_verified = True
                    break

            if not parentage_verified:
                issues.append("Parentage link lacks contemporary documentary corroboration")

        # 4. Calculate Confidence Score (0.0 to 100.0)
        score = 0.0
        if total_sources == 0:
            confidence_level = "UNSOURCED"
            score = 0.0
        else:
            # Weight components
            if parentage_verified:
                score += 40.0
            elif has_parents:
                score += 15.0  # partial credit for asserted relationships

            if birth_verified:
                score += 30.0
            elif person and person.get("birth_date"):
                score += 10.0  # unverified birth assertion

            if death_verified:
                score += 20.0
            elif person and person.get("living"):
                score += 20.0  # living persons get full death credit
            elif person and person.get("death_date"):
                score += 5.0

            # Corroborating primary depth (multiple Tier 1 sources)
            corrob_bonus = min(tier1_count * 2.0, 10.0)
            score += corrob_bonus

            # Tier 2 bonus
            score += min(tier2_count * 1.0, 5.0)

            # Cap / penalties
            if tier1_count == 0 and tier2_count == 0 and tier3_count > 0:
                # Pure user trees get capped at low confidence
                score = min(score, 25.0)
                issues.append("Relies exclusively on Tier 3 user trees or member submissions")

            score = min(max(score, 0.0), 100.0)

            if score >= 80.0:
                confidence_level = "HIGH"
            elif score >= 50.0:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"

        assessment = AuditAssessment(
            person_pid=pid,
            name=person_name,
            total_sources=total_sources,
            tier1_sources=tier1_count,
            tier2_sources=tier2_count,
            tier3_sources=tier3_count,
            birth_verified=birth_verified,
            death_verified=death_verified,
            parentage_verified=parentage_verified,
            confidence_score=round(score, 1),
            confidence_level=confidence_level,
            issues=issues,
        )

        # Store assessment in database
        self.db.upsert_audit_score(
            {
                "person_pid": pid,
                "total_sources": total_sources,
                "tier1_sources": tier1_count,
                "tier2_sources": tier2_count,
                "tier3_sources": tier3_count,
                "birth_verified": birth_verified,
                "death_verified": death_verified,
                "parentage_verified": parentage_verified,
                "confidence_score": score,
                "confidence_level": confidence_level,
                "issues": issues,
            }
        )

        return assessment

    def audit_pedigree(
        self,
        root_pid: str,
        fetch: bool = False,
        refresh: bool = False,
        only_missing: bool = True,
        max_generation: int | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> list[AuditAssessment]:
        """Audits all ancestors in the pedigree of root_pid."""
        pedigree = self.db.get_pedigree(root_pid)
        if max_generation is not None:
            pedigree = [p for p in pedigree if p.get("generation", 0) <= max_generation]
        total = len(pedigree)

        assessments = []
        for idx, person in enumerate(pedigree):
            pid = person["pid"]
            name = person["name"]

            if fetch:
                should_fetch = True
                if only_missing and not refresh:
                    if self.db.has_person_sources(pid):
                        should_fetch = False

                if should_fetch:
                    if progress_callback:
                        progress_callback(f"Fetching sources for {name}", idx + 1, total)
                    self.fetch_and_store_person_sources(pid)
                    time.sleep(0.08)  # polite throttle for FamilySearch API

            if progress_callback:
                progress_callback(f"Auditing evidence for {name}", idx + 1, total)

            assessment = self.audit_person(pid)
            assessment.generation = person["generation"]
            assessments.append(assessment)

        return assessments
