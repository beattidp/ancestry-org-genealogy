"""Targeted Synchronization Engine for FamilySearch GEDCOM X REST API.

Bridges local discoveries and geospatial enhancements from data/pedigree.sqlite
to FamilySearch Tree records using selective, GPS-justified write operations.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import sqlite3
from typing import Any

from src.familysearch.client import FamilySearchClient, FamilySearchAPIError, FamilySearchAuthError
from src.geo.scottish_gazetteer import ScottishGazetteer, ScottishParish


class SyncActionType(str, Enum):
    """Types of targeted synchronization actions supported."""

    ATTACH_SOURCE = "ATTACH_SOURCE"
    UPDATE_FACT = "UPDATE_FACT"
    CREATE_RELATIONSHIP = "CREATE_RELATIONSHIP"


@dataclass
class DiscoverySyncRecord:
    """Encapsulates a staged discovery mutation targeting a FamilySearch PID."""

    record_id: str
    target_pid: str
    action_type: SyncActionType
    title: str
    evidence_url: str | None = None
    citation: str | None = None
    fact_type: str | None = None
    date_str: str | None = None
    place_str: str | None = None
    place_coordinates: tuple[float, float] | None = None
    change_message: str = ""
    gedcomx_payload: dict[str, Any] = field(default_factory=dict)
    status: str = "staged"  # 'staged', 'synced', 'skipped', 'failed'
    error_message: str | None = None


@dataclass
class SyncReport:
    """Summary report of staged or executed synchronization actions."""

    total_staged: int = 0
    total_synced: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    dry_run: bool = True
    records: list[DiscoverySyncRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SyncEngine:
    """Orchestrates targeted updates from pedigree database to FamilySearch."""

    def __init__(
        self,
        db_path: Path | str = "data/pedigree.sqlite",
        client: FamilySearchClient | None = None,
        gazetteer: ScottishGazetteer | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.client = client or FamilySearchClient()
        self.gazetteer = gazetteer or ScottishGazetteer()

    def _get_connection(self) -> sqlite3.Connection:
        """Establishes SQLite connection with row dictionary access."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------------------
    # Staging Discoveries
    # -------------------------------------------------------------------------

    def stage_candidate_discoveries(
        self,
        min_confidence: float = 0.70,
        only_confirmed: bool = True,
    ) -> list[DiscoverySyncRecord]:
        """Stages candidate discoveries (e.g. newspaper mentions, monographs) for source attachment."""
        if not self.db_path.exists():
            return []

        staged: list[DiscoverySyncRecord] = []

        with self._get_connection() as conn:
            query = "SELECT * FROM candidate_discoveries WHERE 1=1"
            params: list[Any] = []
            if only_confirmed:
                query += " AND status = 'confirmed'"
            else:
                query += " AND (status = 'confirmed' OR (status = 'pending' AND confidence_score >= ?))"
                params.append(min_confidence)

            query += " ORDER BY confidence_score DESC, id ASC"
            rows = conn.execute(query, params).fetchall()

            for row in rows:
                cid = row["id"]
                pid = row["person_pid"]
                title = row["title"]
                url = row["url"] or ""
                date_str = row["date_str"] or ""
                harvester = row["harvester"]
                reason = row["relevance_reason"] or "High confidence record match"
                snippet = row["snippet_text"] or ""

                citation_text = f"{title}"
                if date_str:
                    citation_text += f" ({date_str})"
                if snippet:
                    citation_text += f". Snippet: {snippet[:150]}"

                change_msg = (
                    f"Verified via {title}"
                    f"{f' ({date_str})' if date_str else ''}. "
                    f"Evidence rationale: {reason}. Harvester: {harvester}."
                )

                # Construct GEDCOM X payload representation
                source_description = {
                    "about": url,
                    "titles": [{"value": title}],
                    "citations": [{"value": citation_text}],
                    "attribution": {"changeMessage": change_msg},
                }

                staged.append(
                    DiscoverySyncRecord(
                        record_id=f"candidate_discovery:{cid}",
                        target_pid=pid,
                        action_type=SyncActionType.ATTACH_SOURCE,
                        title=title,
                        evidence_url=url,
                        citation=citation_text,
                        change_message=change_msg,
                        gedcomx_payload={"sourceDescriptions": [source_description]},
                        status="staged",
                    )
                )

        return staged

    def stage_scottish_parish_updates(self) -> list[DiscoverySyncRecord]:
        """Stages Scottish vital events where place has been resolved to an NRS civil parish."""
        if not self.db_path.exists():
            return []

        staged: list[DiscoverySyncRecord] = []

        with self._get_connection() as conn:
            query = """
                SELECT id, person_pid, fact_type, date_original, date_formal, place_original
                FROM facts
                WHERE (place_original LIKE '%Scotland%' OR place_original LIKE '%Scottish%')
                  AND fact_type IN ('Birth', 'Christening', 'Death', 'Burial')
                ORDER BY person_pid, fact_type
            """
            rows = conn.execute(query).fetchall()

            for row in rows:
                fid = row["id"]
                pid = row["person_pid"]
                fact_type = row["fact_type"]
                date_orig = row["date_original"]
                date_formal = row["date_formal"]
                place_orig = row["place_original"]

                parish, county = self.gazetteer.resolve_place(place_orig)
                if not parish or not parish.coordinates:
                    continue

                lat, lon = parish.coordinates
                standardized_place = f"{parish.parish_name}, {parish.county}, Scotland"

                change_msg = (
                    f"Standardized Scottish Civil Parish to {parish.parish_name} "
                    f"(NRS Parish #{parish.parish_number}, {parish.county}) "
                    f"with coordinates ({lat:.4f}, {lon:.4f}) based on National Records of Scotland OPR gazetteer."
                )

                fact_payload: dict[str, Any] = {
                    "type": f"http://gedcomx.org/{fact_type}",
                    "place": {"original": standardized_place, "description": "#place-ref"},
                    "attribution": {"changeMessage": change_msg},
                }
                if date_orig:
                    fact_payload["date"] = {"original": date_orig}
                    if date_formal:
                        fact_payload["date"]["formal"] = date_formal

                payload: dict[str, Any] = {
                    "persons": [{"id": pid, "facts": [fact_payload]}],
                    "places": [
                        {
                            "id": "place-ref",
                            "names": [{"value": standardized_place}],
                            "latitude": lat,
                            "longitude": lon,
                        }
                    ],
                }

                staged.append(
                    DiscoverySyncRecord(
                        record_id=f"scottish_fact:{fid}",
                        target_pid=pid,
                        action_type=SyncActionType.UPDATE_FACT,
                        title=f"{fact_type} in {parish.parish_name} (#{parish.parish_number})",
                        fact_type=fact_type,
                        date_str=date_orig,
                        place_str=standardized_place,
                        place_coordinates=(lat, lon),
                        change_message=change_msg,
                        gedcomx_payload=payload,
                        status="staged",
                    )
                )

        return staged

    # -------------------------------------------------------------------------
    # Execution & Synchronization
    # -------------------------------------------------------------------------

    def execute_sync(
        self,
        records: list[DiscoverySyncRecord],
        dry_run: bool = True,
    ) -> SyncReport:
        """Executes or dry-run previews the synchronization records against FamilySearch."""
        report = SyncReport(total_staged=len(records), dry_run=dry_run, records=records)

        for record in records:
            # Pre-validation for all records
            if not record.target_pid or not record.target_pid.strip():
                record.status = "failed"
                record.error_message = "Missing target PID"
                report.total_failed += 1
                report.errors.append(f"{record.record_id}: Missing target PID")
                continue

            if not record.change_message or not record.change_message.strip():
                record.status = "failed"
                record.error_message = "Mandatory changeMessage justification is missing"
                report.total_failed += 1
                report.errors.append(f"{record.record_id}: Missing changeMessage")
                continue

            if dry_run:
                # Validated but not dispatched over network
                record.status = "staged"
                report.total_synced += 1
                continue

            # Live network execution
            try:
                if record.action_type == SyncActionType.ATTACH_SOURCE:
                    if not record.evidence_url:
                        record.status = "skipped"
                        record.error_message = "Source attachment missing evidence URL"
                        report.total_skipped += 1
                        continue

                    self.client.add_person_source_citation(
                        pid=record.target_pid,
                        url=record.evidence_url,
                        title=record.title,
                        citation=record.citation or record.title,
                        change_message=record.change_message,
                    )
                    record.status = "synced"
                    report.total_synced += 1

                    # Update local status in SQLite
                    if record.record_id.startswith("candidate_discovery:"):
                        cid = int(record.record_id.split(":")[1])
                        self._update_candidate_discovery_status(cid, "synced")

                elif record.action_type == SyncActionType.UPDATE_FACT:
                    self.client.add_or_update_person_fact(
                        pid=record.target_pid,
                        fact_type=record.fact_type or "Birth",
                        date_original=record.date_str,
                        place_original=record.place_str,
                        change_message=record.change_message,
                        place_coordinates=record.place_coordinates,
                    )
                    record.status = "synced"
                    report.total_synced += 1

                else:
                    record.status = "skipped"
                    record.error_message = f"Unsupported action type: {record.action_type}"
                    report.total_skipped += 1

            except (FamilySearchAuthError, FamilySearchAPIError, Exception) as exc:
                record.status = "failed"
                record.error_message = str(exc)
                report.total_failed += 1
                report.errors.append(f"{record.record_id} ({record.target_pid}): {exc}")

        return report

    def _update_candidate_discovery_status(self, discovery_id: int, status: str) -> None:
        """Updates the status column of candidate_discoveries table."""
        if not self.db_path.exists():
            return
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE candidate_discoveries SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, discovery_id),
            )
            conn.commit()

    @staticmethod
    def format_summary_table(report: SyncReport) -> str:
        """Renders an ASCII/Markdown table of sync results for review."""
        lines = [
            f"# FamilySearch Synchronization Report ({'DRY-RUN' if report.dry_run else 'LIVE EXECUTION'})",
            "",
            f"- **Total Staged:** {report.total_staged}",
            f"- **Total Synced/Validated:** {report.total_synced}",
            f"- **Total Skipped:** {report.total_skipped}",
            f"- **Total Failed:** {report.total_failed}",
            "",
            "| Record ID | Target PID | Action | Title / Description | Status | Rationale |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for r in report.records:
            msg_snippet = (r.change_message[:60] + "...") if len(r.change_message) > 60 else r.change_message
            title_snippet = (r.title[:45] + "...") if len(r.title) > 45 else r.title
            lines.append(
                f"| `{r.record_id}` | `{r.target_pid}` | `{r.action_type.value}` | "
                f"{title_snippet} | **{r.status.upper()}** | {msg_snippet} |"
            )

        if report.errors:
            lines.extend(["", "### Errors Encountered:"])
            for err in report.errors:
                lines.append(f"- ❌ {err}")

        return "\n".join(lines)


def main() -> None:
    """CLI entrypoint for targeted FamilySearch discovery synchronization."""
    parser = argparse.ArgumentParser(
        description="Targeted synchronization of verified discoveries to FamilySearch via GEDCOM X REST API."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute live network writes against FamilySearch (default is dry-run mode).",
    )
    parser.add_argument(
        "--include-pending",
        action="store_true",
        help="Include pending high-confidence candidate discoveries (confidence >= 0.70).",
    )
    parser.add_argument(
        "--env",
        choices=["production", "beta", "sandbox", "integration"],
        default=None,
        help="Target FamilySearch environment ('beta'/'sandbox' or 'production'). Overrides FAMILYSEARCH_ENV in .env.",
    )
    parser.add_argument(
        "--pid",
        type=str,
        default=None,
        help="Filter synchronization to a specific PID (e.g. '9ZMG-JSD').",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.70,
        help="Minimum confidence threshold for pending discoveries (default: 0.70).",
    )
    parser.add_argument(
        "--include-scottish-parishes",
        action="store_true",
        default=True,
        help="Include Scottish civil parish coordinate standardization (default: True).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to pedigree SQLite database (default: data/pedigree.sqlite).",
    )

    args = parser.parse_args()

    from src.config import Settings
    settings = Settings()
    if args.env:
        settings.familysearch_env = args.env

    client = FamilySearchClient(settings=settings)

    if args.live:
        session_status = client.session_manager.validate_session()
        print(f"Targeting FamilySearch: {settings.base_url}")
        if not session_status.is_valid:
            print(f"❌ Session validation failed for {settings.base_url} ({session_status.status_code}): {session_status.message}")
            if settings.familysearch_env == "beta":
                print(
                    "\n[!] Notice: Production tokens (from familysearch.org) are not recognized by apibeta.familysearch.org. "
                    "To post to apibeta, log into https://beta.familysearch.org and copy the fssessionid cookie to .env, "
                    "or configure a Developer App Key for the Beta integration system."
                )
            return
        print(f"✓ Authenticated as: {session_status.display_name} ({session_status.user_id})\n")

    engine = SyncEngine(db_path=args.db, client=client)
    staged: list[DiscoverySyncRecord] = []

    # 1. Candidate discoveries
    candidate_records = engine.stage_candidate_discoveries(
        min_confidence=args.min_confidence,
        only_confirmed=not args.include_pending,
    )
    staged.extend(candidate_records)

    # 2. Scottish parish enhancements
    if args.include_scottish_parishes:
        parish_records = engine.stage_scottish_parish_updates()
        staged.extend(parish_records)

    # 3. Optional PID filter
    if args.pid:
        target_pid = args.pid.strip().upper()
        staged = [r for r in staged if r.target_pid.upper() == target_pid]
        if not staged:
            print(f"No staged records found matching target PID: {target_pid}")
            return

    dry_run = not args.live
    report = engine.execute_sync(staged, dry_run=dry_run)
    print(engine.format_summary_table(report))


if __name__ == "__main__":
    main()

