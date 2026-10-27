"""Engine coordinating biological and chronological validation across pedigree trees."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.constraints.rules import (
    Violation,
    check_individual_chronology,
    check_parent_child_biology,
    check_spousal_chronology,
)
from src.storage.db import Database


@dataclass
class ValidationReport:
    """Detailed results and statistics of a constraint validation run."""

    total_persons: int
    total_relationships: int
    violations: list[Violation]
    error_count: int
    warning_count: int
    info_count: int
    pass_rate: float
    violations_by_rule: dict[str, int]
    affected_persons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_persons": self.total_persons,
            "total_relationships": self.total_relationships,
            "total_violations": len(self.violations),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "pass_rate": self.pass_rate,
            "violations_by_rule": self.violations_by_rule,
            "affected_persons": self.affected_persons,
        }


class ConstraintEngine:
    """Coordinates deterministic constraint validation on pedigree graphs stored in SQLite."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def validate(
        self,
        root_pid: Optional[str] = None,
        person_pid: Optional[str] = None,
        min_confidence: Optional[float] = None,
        persist: bool = False,
    ) -> ValidationReport:
        """Runs all biological and chronological constraint checks.

        Args:
            root_pid: If specified, validates all ancestors in the pedigree of root_pid.
            person_pid: If specified, validates only this single person and their direct links.
            min_confidence: If specified, filters evaluation to persons with confidence_score >= min_confidence.
            persist: If True, writes detected violations to SQLite table constraint_violations.
        """
        # 1. Fetch Target Persons
        persons_map: dict[str, dict[str, Any]] = {}
        person_gen_map: dict[str, int] = {}

        with self.db.get_connection() as conn:
            if person_pid:
                row = conn.execute("SELECT * FROM persons WHERE pid = ?", (person_pid,)).fetchone()
                if row:
                    persons_map[person_pid] = dict(row)
            elif root_pid:
                # Query pedigree tree for root_pid
                query = """
                SELECT p.*, pt.generation, pt.ascendancy_number, pt.lineage_path,
                       COALESCE(sc.confidence_score, 0.0) AS confidence_score
                FROM pedigree_tree pt
                JOIN persons p ON pt.person_pid = p.pid
                LEFT JOIN person_audit_scores sc ON p.pid = sc.person_pid
                WHERE pt.root_pid = ?
                """
                params: list[Any] = [root_pid]
                if min_confidence is not None:
                    query += " AND COALESCE(sc.confidence_score, 0.0) >= ?"
                    params.append(min_confidence)

                rows = conn.execute(query, params).fetchall()
                for r in rows:
                    d = dict(r)
                    pid = d["pid"]
                    persons_map[pid] = d
                    if "generation" in d:
                        person_gen_map[pid] = d["generation"]
            else:
                # All persons in database
                query = """
                SELECT p.*, COALESCE(sc.confidence_score, 0.0) AS confidence_score
                FROM persons p
                LEFT JOIN person_audit_scores sc ON p.pid = sc.person_pid
                """
                params = []
                if min_confidence is not None:
                    query += " WHERE COALESCE(sc.confidence_score, 0.0) >= ?"
                    params.append(min_confidence)

                rows = conn.execute(query, params).fetchall()
                for r in rows:
                    d = dict(r)
                    persons_map[d["pid"]] = d

        if not persons_map:
            return ValidationReport(
                total_persons=0,
                total_relationships=0,
                violations=[],
                error_count=0,
                warning_count=0,
                info_count=0,
                pass_rate=100.0,
                violations_by_rule={},
            )

        # 2. Fetch Facts for Target Persons
        all_pids = list(persons_map.keys())
        facts_by_person: dict[str, list[dict[str, Any]]] = {pid: [] for pid in all_pids}

        with self.db.get_connection() as conn:
            # Batch query facts
            chunk_size = 500
            for i in range(0, len(all_pids), chunk_size):
                chunk = all_pids[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"SELECT * FROM facts WHERE person_pid IN ({placeholders})", chunk
                ).fetchall()
                for r in rows:
                    f = dict(r)
                    facts_by_person[f["person_pid"]].append(f)

        # 3. Fetch Relevant Relationships
        relationships: list[dict[str, Any]] = []
        with self.db.get_connection() as conn:
            chunk_size = 500
            for i in range(0, len(all_pids), chunk_size):
                chunk = all_pids[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT * FROM relationships
                    WHERE child_pid IN ({placeholders})
                       OR parent_pid IN ({placeholders})
                       OR spouse1_pid IN ({placeholders})
                       OR spouse2_pid IN ({placeholders})
                    """,
                    chunk * 4,
                ).fetchall()
                for r in rows:
                    relationships.append(dict(r))

        # Deduplicate relationships by ID
        unique_rels: dict[str, dict[str, Any]] = {}
        for r in relationships:
            unique_rels[r["id"]] = r

        # Ensure related persons outside the target set are loaded for relational rules
        missing_rel_pids = set()
        for r in unique_rels.values():
            for key in ["parent_pid", "child_pid", "spouse1_pid", "spouse2_pid"]:
                p = r.get(key)
                if p and p not in persons_map:
                    missing_rel_pids.add(p)

        if missing_rel_pids:
            with self.db.get_connection() as conn:
                placeholders = ",".join("?" for _ in missing_rel_pids)
                p_rows = conn.execute(
                    f"SELECT * FROM persons WHERE pid IN ({placeholders})",
                    list(missing_rel_pids),
                ).fetchall()
                for r in p_rows:
                    d = dict(r)
                    persons_map[d["pid"]] = d
                    facts_by_person[d["pid"]] = []

                f_rows = conn.execute(
                    f"SELECT * FROM facts WHERE person_pid IN ({placeholders})",
                    list(missing_rel_pids),
                ).fetchall()
                for r in f_rows:
                    f = dict(r)
                    facts_by_person[f["person_pid"]].append(f)

        # 4. Execute Constraint Rules
        violations: list[Violation] = []
        seen_violations = set()

        def add_violation(v: Violation) -> None:
            key = (v.rule_id, v.person_pid, v.relative_pid, v.description)
            if key not in seen_violations:
                seen_violations.add(key)
                violations.append(v)

        # A. Individual Chronology Rules
        for pid in all_pids:
            person = persons_map[pid]
            facts = facts_by_person.get(pid, [])
            indiv_violations = check_individual_chronology(person, facts)
            for v in indiv_violations:
                add_violation(v)

        # B. Parent-Child Biological Rules
        for r in unique_rels.values():
            rtype = r.get("relationship_type")
            parent_pid = r.get("parent_pid")
            child_pid = r.get("child_pid")

            if parent_pid and child_pid:
                # Only check if child or parent is in our evaluated set
                if child_pid in all_pids or parent_pid in all_pids:
                    parent = persons_map.get(parent_pid)
                    child = persons_map.get(child_pid)
                    if parent and child:
                        p_facts = facts_by_person.get(parent_pid, [])
                        c_facts = facts_by_person.get(child_pid, [])
                        pc_violations = check_parent_child_biology(
                            parent=parent,
                            child=child,
                            relationship_type=rtype or "parent",
                            parent_facts=p_facts,
                            child_facts=c_facts,
                        )
                        for v in pc_violations:
                            add_violation(v)

        # C. Spousal Chronology Rules
        for r in unique_rels.values():
            rtype = r.get("relationship_type")
            if rtype == "couple" or (r.get("spouse1_pid") and r.get("spouse2_pid")):
                s1_pid = r.get("spouse1_pid")
                s2_pid = r.get("spouse2_pid")
                if s1_pid and s2_pid and (s1_pid in all_pids or s2_pid in all_pids):
                    s1 = persons_map.get(s1_pid)
                    s2 = persons_map.get(s2_pid)
                    if s1 and s2:
                        s1_facts = facts_by_person.get(s1_pid, [])
                        s2_facts = facts_by_person.get(s2_pid, [])
                        sp_violations = check_spousal_chronology(
                            husband=s1,
                            wife=s2,
                            marriage_fact=r,
                            husband_facts=s1_facts,
                            wife_facts=s2_facts,
                        )
                        for v in sp_violations:
                            add_violation(v)

        # 5. Summarize Metrics
        error_count = sum(1 for v in violations if v.severity == "ERROR")
        warning_count = sum(1 for v in violations if v.severity == "WARNING")
        info_count = sum(1 for v in violations if v.severity == "INFO")

        error_pids = {v.person_pid for v in violations if v.severity == "ERROR"}
        pass_rate = round(
            ((len(all_pids) - len(error_pids)) / len(all_pids)) * 100.0, 1
        ) if all_pids else 100.0

        rule_counts: dict[str, int] = {}
        for v in violations:
            rule_counts[v.rule_id] = rule_counts.get(v.rule_id, 0) + 1

        affected_pids = sorted(list({v.person_pid for v in violations}))

        report = ValidationReport(
            total_persons=len(all_pids),
            total_relationships=len(unique_rels),
            violations=violations,
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            pass_rate=pass_rate,
            violations_by_rule=rule_counts,
            affected_persons=affected_pids,
        )

        # 6. Optional Persistence
        if persist:
            raw_violations = [v.to_dict() for v in violations]
            self.db.record_violations_batch(
                violations=raw_violations,
                clear_existing=True,
                person_pid=person_pid,
            )

        return report
