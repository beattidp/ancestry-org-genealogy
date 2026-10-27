"""SQLite storage manager for genealogical records, relationships, and pedigree trees."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


def _to_text(v: Any) -> str | None:
    """Safely converts arbitrary values to string for SQLite text binding."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)


class Database:
    """Manages SQLite connections and operations for the genealogy database."""

    def __init__(self, db_path: str | Path = "data/pedigree.sqlite") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Initializes database schema and indexes."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS persons (
                    pid TEXT PRIMARY KEY,
                    name TEXT,
                    gender TEXT,
                    lifespan TEXT,
                    living INTEGER DEFAULT 0,
                    birth_date TEXT,
                    birth_place TEXT,
                    death_date TEXT,
                    death_place TEXT,
                    raw_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT PRIMARY KEY,
                    rel_type TEXT,
                    parent_pid TEXT,
                    child_pid TEXT,
                    spouse1_pid TEXT,
                    spouse2_pid TEXT,
                    lineage_type TEXT,
                    raw_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS pedigree_tree (
                    root_pid TEXT,
                    person_pid TEXT,
                    generation INTEGER,
                    ascendancy_number INTEGER,
                    lineage_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (root_pid, person_pid),
                    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_pid TEXT,
                    fact_type TEXT,
                    date_original TEXT,
                    date_formal TEXT,
                    place_original TEXT,
                    place_normalized TEXT,
                    value TEXT,
                    raw_json TEXT,
                    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_pid TEXT,
                    max_generations INTEGER,
                    persons_ingested INTEGER DEFAULT 0,
                    relationships_ingested INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'running'
                );

                CREATE INDEX IF NOT EXISTS idx_facts_person ON facts(person_pid, fact_type);
                CREATE INDEX IF NOT EXISTS idx_rel_parent ON relationships(parent_pid);
                CREATE INDEX IF NOT EXISTS idx_rel_child ON relationships(child_pid);
                CREATE INDEX IF NOT EXISTS idx_rel_spouses ON relationships(spouse1_pid, spouse2_pid);
                CREATE INDEX IF NOT EXISTS idx_pedigree_root_gen ON pedigree_tree(root_pid, generation);
                CREATE INDEX IF NOT EXISTS idx_pedigree_asc ON pedigree_tree(root_pid, ascendancy_number);
                """
            )

    # -------------------------------------------------------------------------
    # Ingestion & Upsert Operations
    # -------------------------------------------------------------------------

    def upsert_person(self, person: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
        """Upserts a person record into the persons table."""
        sql = """
        INSERT INTO persons (
            pid, name, gender, lifespan, living,
            birth_date, birth_place, death_date, death_place,
            raw_json, updated_at
        ) VALUES (
            :pid, :name, :gender, :lifespan, :living,
            :birth_date, :birth_place, :death_date, :death_place,
            :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(pid) DO UPDATE SET
            name = excluded.name,
            gender = excluded.gender,
            lifespan = excluded.lifespan,
            living = excluded.living,
            birth_date = excluded.birth_date,
            birth_place = excluded.birth_place,
            death_date = excluded.death_date,
            death_place = excluded.death_place,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP;
        """
        raw_json_str = json.dumps(person.get("raw_json", {})) if isinstance(person.get("raw_json"), (dict, list)) else person.get("raw_json")

        payload = {
            "pid": str(person["pid"]),
            "name": _to_text(person.get("name")),
            "gender": _to_text(person.get("gender")),
            "lifespan": _to_text(person.get("lifespan")),
            "living": 1 if person.get("living") else 0,
            "birth_date": _to_text(person.get("birth_date")),
            "birth_place": _to_text(person.get("birth_place")),
            "death_date": _to_text(person.get("death_date")),
            "death_place": _to_text(person.get("death_place")),
            "raw_json": raw_json_str,
        }

        if conn is not None:
            conn.execute(sql, payload)
        else:
            with self.get_connection() as c:
                c.execute(sql, payload)

    def upsert_persons_batch(self, persons: Sequence[dict[str, Any]]) -> None:
        """Batch upsert persons within a single transaction."""
        with self.get_connection() as conn:
            for p in persons:
                self.upsert_person(p, conn=conn)

    def upsert_relationship(self, rel: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
        """Upserts a relationship record into the relationships table."""
        sql = """
        INSERT INTO relationships (
            id, rel_type, parent_pid, child_pid,
            spouse1_pid, spouse2_pid, lineage_type, raw_json, updated_at
        ) VALUES (
            :id, :rel_type, :parent_pid, :child_pid,
            :spouse1_pid, :spouse2_pid, :lineage_type, :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            rel_type = excluded.rel_type,
            parent_pid = excluded.parent_pid,
            child_pid = excluded.child_pid,
            spouse1_pid = excluded.spouse1_pid,
            spouse2_pid = excluded.spouse2_pid,
            lineage_type = excluded.lineage_type,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP;
        """
        raw_json_str = json.dumps(rel.get("raw_json", {})) if isinstance(rel.get("raw_json"), (dict, list)) else rel.get("raw_json")

        payload = {
            "id": rel["id"],
            "rel_type": rel.get("rel_type", "parent-child"),
            "parent_pid": rel.get("parent_pid"),
            "child_pid": rel.get("child_pid"),
            "spouse1_pid": rel.get("spouse1_pid"),
            "spouse2_pid": rel.get("spouse2_pid"),
            "lineage_type": rel.get("lineage_type"),
            "raw_json": raw_json_str,
        }

        if conn is not None:
            conn.execute(sql, payload)
        else:
            with self.get_connection() as c:
                c.execute(sql, payload)

    def upsert_relationships_batch(self, relationships: Sequence[dict[str, Any]]) -> None:
        """Batch upsert relationships within a single transaction."""
        with self.get_connection() as conn:
            for r in relationships:
                self.upsert_relationship(r, conn=conn)

    def upsert_pedigree_node(
        self,
        root_pid: str,
        person_pid: str,
        generation: int,
        ascendancy_number: int | None = None,
        lineage_path: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Upserts a pedigree tree node mapping relative to root person."""
        sql = """
        INSERT INTO pedigree_tree (
            root_pid, person_pid, generation, ascendancy_number, lineage_path, updated_at
        ) VALUES (
            :root_pid, :person_pid, :generation, :ascendancy_number, :lineage_path, CURRENT_TIMESTAMP
        )
        ON CONFLICT(root_pid, person_pid) DO UPDATE SET
            generation = excluded.generation,
            ascendancy_number = excluded.ascendancy_number,
            lineage_path = excluded.lineage_path,
            updated_at = CURRENT_TIMESTAMP;
        """
        payload = {
            "root_pid": root_pid,
            "person_pid": person_pid,
            "generation": generation,
            "ascendancy_number": ascendancy_number,
            "lineage_path": lineage_path,
        }

        if conn is not None:
            conn.execute(sql, payload)
        else:
            with self.get_connection() as c:
                c.execute(sql, payload)

    def replace_facts(
        self, person_pid: str, facts: Sequence[dict[str, Any]], conn: sqlite3.Connection | None = None
    ) -> None:
        """Replaces all granular facts for a person."""
        delete_sql = "DELETE FROM facts WHERE person_pid = ?"
        insert_sql = """
        INSERT INTO facts (
            person_pid, fact_type, date_original, date_formal,
            place_original, place_normalized, value, raw_json
        ) VALUES (
            :person_pid, :fact_type, :date_original, :date_formal,
            :place_original, :place_normalized, :value, :raw_json
        );
        """

        def _execute(target_conn: sqlite3.Connection) -> None:
            target_conn.execute(delete_sql, (person_pid,))
            for f in facts:
                raw_json_str = json.dumps(f.get("raw_json", {})) if isinstance(f.get("raw_json"), (dict, list)) else f.get("raw_json")
                target_conn.execute(
                    insert_sql,
                    {
                        "person_pid": person_pid,
                        "fact_type": _to_text(f.get("fact_type")),
                        "date_original": _to_text(f.get("date_original")),
                        "date_formal": _to_text(f.get("date_formal")),
                        "place_original": _to_text(f.get("place_original")),
                        "place_normalized": _to_text(f.get("place_normalized")),
                        "value": _to_text(f.get("value")),
                        "raw_json": raw_json_str,
                    },
                )

        if conn is not None:
            _execute(conn)
        else:
            with self.get_connection() as c:
                _execute(c)

    # -------------------------------------------------------------------------
    # Run Tracking
    # -------------------------------------------------------------------------

    def start_ingestion_run(self, root_pid: str, max_generations: int) -> int:
        """Logs the start of an ingestion run and returns the run ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ingestion_runs (root_pid, max_generations, status)
                VALUES (?, ?, 'running');
                """,
                (root_pid, max_generations),
            )
            return cursor.lastrowid

    def finish_ingestion_run(
        self, run_id: int, persons_count: int, rels_count: int, status: str = "completed"
    ) -> None:
        """Updates an ingestion run with final metrics and status."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_runs
                SET persons_ingested = ?,
                    relationships_ingested = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    status = ?
                WHERE id = ?;
                """,
                (persons_count, rels_count, status, run_id),
            )

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    def get_person(self, pid: str) -> dict[str, Any] | None:
        """Retrieves a single person record by PID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM persons WHERE pid = ?", (pid,)).fetchone()
            return dict(row) if row else None

    def get_pedigree(self, root_pid: str) -> list[dict[str, Any]]:
        """Retrieves all ancestors linked to root_pid, ordered by generation and ascendancy."""
        sql = """
        SELECT
            pt.generation,
            pt.ascendancy_number,
            pt.lineage_path,
            p.pid,
            p.name,
            p.gender,
            p.lifespan,
            p.birth_date,
            p.birth_place,
            p.death_date,
            p.death_place
        FROM pedigree_tree pt
        JOIN persons p ON pt.person_pid = p.pid
        WHERE pt.root_pid = ?
        ORDER BY pt.generation ASC, pt.ascendancy_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (root_pid,)).fetchall()
            return [dict(r) for r in rows]

    def get_pedigree_stats(self, root_pid: str) -> dict[str, Any]:
        """Calculates generational coverage statistics for a pedigree."""
        sql = """
        SELECT
            generation,
            COUNT(*) as count
        FROM pedigree_tree
        WHERE root_pid = ?
        GROUP BY generation
        ORDER BY generation ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (root_pid,)).fetchall()

        by_gen = {}
        total = 0
        for r in rows:
            gen = r["generation"]
            cnt = r["count"]
            expected = 1 if gen == 0 else 2**gen
            by_gen[gen] = {
                "count": cnt,
                "expected": expected,
                "completeness": round((cnt / expected) * 100, 1),
            }
            total += cnt

        return {
            "root_pid": root_pid,
            "total_ancestors": total,
            "generations": by_gen,
        }

    def get_pedigree_gaps(self, root_pid: str, max_generation: int = 4) -> list[dict[str, Any]]:
        """Identifies ancestors in the pedigree who are missing a mother or father."""
        sql = """
        SELECT
            pt.generation,
            pt.ascendancy_number,
            p.pid,
            p.name,
            p.gender,
            p.lifespan,
            (
                SELECT r.parent_pid
                FROM relationships r
                JOIN persons par ON r.parent_pid = par.pid
                WHERE r.child_pid = p.pid AND par.gender = 'Male'
                LIMIT 1
            ) AS father_pid,
            (
                SELECT r.parent_pid
                FROM relationships r
                JOIN persons par ON r.parent_pid = par.pid
                WHERE r.child_pid = p.pid AND par.gender = 'Female'
                LIMIT 1
            ) AS mother_pid
        FROM pedigree_tree pt
        JOIN persons p ON pt.person_pid = p.pid
        WHERE pt.root_pid = ? AND pt.generation < ?
        ORDER BY pt.generation ASC, pt.ascendancy_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (root_pid, max_generation)).fetchall()

        gaps = []
        for r in rows:
            missing_parents = []
            if not r["father_pid"]:
                missing_parents.append("Father")
            if not r["mother_pid"]:
                missing_parents.append("Mother")

            if missing_parents:
                gaps.append(
                    {
                        "pid": r["pid"],
                        "name": r["name"],
                        "generation": r["generation"],
                        "ascendancy_number": r["ascendancy_number"],
                        "missing": missing_parents,
                    }
                )
        return gaps
