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

                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    about_url TEXT,
                    citation_text TEXT,
                    collection_url TEXT,
                    tier INTEGER DEFAULT 3,
                    record_type TEXT DEFAULT 'other',
                    raw_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS person_sources (
                    id TEXT PRIMARY KEY,
                    person_pid TEXT,
                    source_id TEXT,
                    tags TEXT,
                    contributor TEXT,
                    raw_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE,
                    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS person_audit_scores (
                    person_pid TEXT PRIMARY KEY,
                    total_sources INTEGER DEFAULT 0,
                    tier1_sources INTEGER DEFAULT 0,
                    tier2_sources INTEGER DEFAULT 0,
                    tier3_sources INTEGER DEFAULT 0,
                    birth_verified INTEGER DEFAULT 0,
                    death_verified INTEGER DEFAULT 0,
                    parentage_verified INTEGER DEFAULT 0,
                    confidence_score REAL DEFAULT 0.0,
                    confidence_level TEXT DEFAULT 'UNSOURCED',
                    issues TEXT,
                    audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS constraint_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    person_pid TEXT NOT NULL,
                    relative_pid TEXT,
                    description TEXT NOT NULL,
                    details_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (person_pid) REFERENCES persons(pid) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_facts_person ON facts(person_pid, fact_type);
                CREATE INDEX IF NOT EXISTS idx_rel_parent ON relationships(parent_pid);
                CREATE INDEX IF NOT EXISTS idx_rel_child ON relationships(child_pid);
                CREATE INDEX IF NOT EXISTS idx_rel_spouses ON relationships(spouse1_pid, spouse2_pid);
                CREATE INDEX IF NOT EXISTS idx_pedigree_root_gen ON pedigree_tree(root_pid, generation);
                CREATE INDEX IF NOT EXISTS idx_pedigree_asc ON pedigree_tree(root_pid, ascendancy_number);
                CREATE INDEX IF NOT EXISTS idx_sources_tier ON sources(tier);
                CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(record_type);
                CREATE INDEX IF NOT EXISTS idx_ps_person ON person_sources(person_pid);
                CREATE INDEX IF NOT EXISTS idx_ps_source ON person_sources(source_id);
                CREATE INDEX IF NOT EXISTS idx_audit_conf ON person_audit_scores(confidence_score);
                CREATE INDEX IF NOT EXISTS idx_violations_person ON constraint_violations(person_pid);
                CREATE INDEX IF NOT EXISTS idx_violations_rule ON constraint_violations(rule_id);
                CREATE INDEX IF NOT EXISTS idx_violations_severity ON constraint_violations(severity);
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

    # -------------------------------------------------------------------------
    # Sources & Audit Operations
    # -------------------------------------------------------------------------

    def upsert_source(self, source: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
        """Upserts a source record into the sources table."""
        sql = """
        INSERT INTO sources (
            id, title, about_url, citation_text, collection_url,
            tier, record_type, raw_json, updated_at
        ) VALUES (
            :id, :title, :about_url, :citation_text, :collection_url,
            :tier, :record_type, :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            about_url = excluded.about_url,
            citation_text = excluded.citation_text,
            collection_url = excluded.collection_url,
            tier = excluded.tier,
            record_type = excluded.record_type,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP;
        """
        raw_json_str = (
            json.dumps(source.get("raw_json", {}))
            if isinstance(source.get("raw_json"), (dict, list))
            else source.get("raw_json")
        )
        payload = {
            "id": source["id"],
            "title": _to_text(source.get("title")),
            "about_url": _to_text(source.get("about_url")),
            "citation_text": _to_text(source.get("citation_text")),
            "collection_url": _to_text(source.get("collection_url")),
            "tier": int(source.get("tier", 3)),
            "record_type": _to_text(source.get("record_type", "other")),
            "raw_json": raw_json_str,
        }
        if conn is not None:
            conn.execute(sql, payload)
        else:
            with self.get_connection() as c:
                c.execute(sql, payload)

    def upsert_sources_batch(self, sources: Sequence[dict[str, Any]]) -> None:
        """Batch upserts source records."""
        with self.get_connection() as conn:
            for s in sources:
                self.upsert_source(s, conn=conn)

    def upsert_person_sources_batch(self, person_sources: Sequence[dict[str, Any]]) -> None:
        """Batch upserts citation reference links between persons and sources."""
        sql = """
        INSERT INTO person_sources (
            id, person_pid, source_id, tags, contributor, raw_json, updated_at
        ) VALUES (
            :id, :person_pid, :source_id, :tags, :contributor, :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            person_pid = excluded.person_pid,
            source_id = excluded.source_id,
            tags = excluded.tags,
            contributor = excluded.contributor,
            raw_json = excluded.raw_json,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            for ps in person_sources:
                raw_json_str = (
                    json.dumps(ps.get("raw_json", {}))
                    if isinstance(ps.get("raw_json"), (dict, list))
                    else ps.get("raw_json")
                )
                payload = {
                    "id": ps["id"],
                    "person_pid": ps["person_pid"],
                    "source_id": ps["source_id"],
                    "tags": _to_text(ps.get("tags")),
                    "contributor": _to_text(ps.get("contributor")),
                    "raw_json": raw_json_str,
                }
                conn.execute(sql, payload)

    def upsert_audit_score(self, score: dict[str, Any], conn: sqlite3.Connection | None = None) -> None:
        """Upserts an audit assessment score for a person."""
        sql = """
        INSERT INTO person_audit_scores (
            person_pid, total_sources, tier1_sources, tier2_sources, tier3_sources,
            birth_verified, death_verified, parentage_verified,
            confidence_score, confidence_level, issues, audited_at
        ) VALUES (
            :person_pid, :total_sources, :tier1_sources, :tier2_sources, :tier3_sources,
            :birth_verified, :death_verified, :parentage_verified,
            :confidence_score, :confidence_level, :issues, CURRENT_TIMESTAMP
        )
        ON CONFLICT(person_pid) DO UPDATE SET
            total_sources = excluded.total_sources,
            tier1_sources = excluded.tier1_sources,
            tier2_sources = excluded.tier2_sources,
            tier3_sources = excluded.tier3_sources,
            birth_verified = excluded.birth_verified,
            death_verified = excluded.death_verified,
            parentage_verified = excluded.parentage_verified,
            confidence_score = excluded.confidence_score,
            confidence_level = excluded.confidence_level,
            issues = excluded.issues,
            audited_at = CURRENT_TIMESTAMP;
        """
        issues_str = (
            json.dumps(score.get("issues", []))
            if isinstance(score.get("issues"), (list, dict))
            else score.get("issues")
        )
        payload = {
            "person_pid": score["person_pid"],
            "total_sources": int(score.get("total_sources", 0)),
            "tier1_sources": int(score.get("tier1_sources", 0)),
            "tier2_sources": int(score.get("tier2_sources", 0)),
            "tier3_sources": int(score.get("tier3_sources", 0)),
            "birth_verified": 1 if score.get("birth_verified") else 0,
            "death_verified": 1 if score.get("death_verified") else 0,
            "parentage_verified": 1 if score.get("parentage_verified") else 0,
            "confidence_score": float(score.get("confidence_score", 0.0)),
            "confidence_level": _to_text(score.get("confidence_level", "UNSOURCED")),
            "issues": issues_str,
        }
        if conn is not None:
            conn.execute(sql, payload)
        else:
            with self.get_connection() as c:
                c.execute(sql, payload)

    def get_person_sources(self, person_pid: str) -> list[dict[str, Any]]:
        """Retrieves all attached sources and citation metadata for a person."""
        sql = """
        SELECT
            ps.id AS citation_id,
            ps.tags,
            ps.contributor,
            s.id AS source_id,
            s.title,
            s.about_url,
            s.citation_text,
            s.collection_url,
            s.tier,
            s.record_type
        FROM person_sources ps
        JOIN sources s ON ps.source_id = s.id
        WHERE ps.person_pid = ?
        ORDER BY s.tier ASC, s.record_type ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, (person_pid,)).fetchall()
            return [dict(r) for r in rows]

    def has_person_sources(self, person_pid: str) -> bool:
        """Checks if any sources are already linked to person_pid."""
        sql = "SELECT 1 FROM person_sources WHERE person_pid = ? LIMIT 1;"
        with self.get_connection() as conn:
            return conn.execute(sql, (person_pid,)).fetchone() is not None

    def get_audit_scores(self, root_pid: str, max_generation: int | None = None) -> list[dict[str, Any]]:
        """Retrieves audit scores for all ancestors in the pedigree of root_pid."""
        where_clause = "WHERE pt.root_pid = ?"
        params: list[Any] = [root_pid]
        if max_generation is not None:
            where_clause += " AND pt.generation <= ?"
            params.append(max_generation)

        sql = f"""
        SELECT
            pt.generation,
            pt.ascendancy_number,
            pt.lineage_path,
            p.pid,
            p.name,
            p.gender,
            p.lifespan,
            COALESCE(sc.total_sources, 0) AS total_sources,
            COALESCE(sc.tier1_sources, 0) AS tier1_sources,
            COALESCE(sc.tier2_sources, 0) AS tier2_sources,
            COALESCE(sc.tier3_sources, 0) AS tier3_sources,
            COALESCE(sc.birth_verified, 0) AS birth_verified,
            COALESCE(sc.death_verified, 0) AS death_verified,
            COALESCE(sc.parentage_verified, 0) AS parentage_verified,
            COALESCE(sc.confidence_score, 0.0) AS confidence_score,
            COALESCE(sc.confidence_level, 'UNSOURCED') AS confidence_level,
            sc.issues
        FROM pedigree_tree pt
        JOIN persons p ON pt.person_pid = p.pid
        LEFT JOIN person_audit_scores sc ON p.pid = sc.person_pid
        {where_clause}
        ORDER BY pt.generation ASC, pt.ascendancy_number ASC;
        """
        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("issues"):
                    try:
                        d["issues"] = json.loads(d["issues"])
                    except Exception:
                        pass
                else:
                    d["issues"] = []
                results.append(d)
            return results

    def get_audit_summary(self, root_pid: str, max_generation: int | None = None) -> dict[str, Any]:
        """Calculates aggregate audit metrics across the pedigree."""
        scores = self.get_audit_scores(root_pid, max_generation=max_generation)
        total = len(scores)
        if total == 0:
            return {
                "total_ancestors": 0,
                "confidence_levels": {},
                "generations": {},
                "avg_confidence": 0.0,
            }

        conf_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNSOURCED": 0}
        gen_stats: dict[int, dict[str, Any]] = {}
        total_score_sum = 0.0

        for s in scores:
            level = s["confidence_level"]
            conf_counts[level] = conf_counts.get(level, 0) + 1
            total_score_sum += s["confidence_score"]

            gen = s["generation"]
            if gen not in gen_stats:
                gen_stats[gen] = {
                    "count": 0,
                    "birth_verified": 0,
                    "death_verified": 0,
                    "parentage_verified": 0,
                    "avg_score": 0.0,
                    "score_sum": 0.0,
                }
            g = gen_stats[gen]
            g["count"] += 1
            if s["birth_verified"]:
                g["birth_verified"] += 1
            if s["death_verified"]:
                g["death_verified"] += 1
            if s["parentage_verified"]:
                g["parentage_verified"] += 1
            g["score_sum"] += s["confidence_score"]

        for gen, g in gen_stats.items():
            g["avg_score"] = round(g["score_sum"] / g["count"], 1) if g["count"] > 0 else 0.0
            del g["score_sum"]

        return {
            "root_pid": root_pid,
            "total_ancestors": total,
            "confidence_levels": conf_counts,
            "generations": gen_stats,
            "avg_confidence": round(total_score_sum / total, 1),
        }

    # -------------------------------------------------------------------------
    # Constraint & Biological Anomaly Operations
    # -------------------------------------------------------------------------

    def clear_violations(self, person_pid: str | None = None) -> int:
        """Clears constraint violations from the database.

        If person_pid is provided, only deletes violations for that person.
        Otherwise deletes all violations.
        """
        with self.get_connection() as conn:
            if person_pid:
                cursor = conn.execute(
                    "DELETE FROM constraint_violations WHERE person_pid = ?",
                    (person_pid,),
                )
            else:
                cursor = conn.execute("DELETE FROM constraint_violations")
            return cursor.rowcount

    def record_violations_batch(
        self,
        violations: list[dict[str, Any]],
        clear_existing: bool = True,
        person_pid: str | None = None,
    ) -> int:
        """Stores a batch of constraint violations into the database.

        If clear_existing is True, clears existing violations beforehand.
        """
        with self.get_connection() as conn:
            if clear_existing:
                if person_pid:
                    conn.execute(
                        "DELETE FROM constraint_violations WHERE person_pid = ?",
                        (person_pid,),
                    )
                else:
                    conn.execute("DELETE FROM constraint_violations")

            sql = """
            INSERT INTO constraint_violations (
                rule_id, severity, person_pid, relative_pid,
                description, details_json, created_at
            ) VALUES (
                :rule_id, :severity, :person_pid, :relative_pid,
                :description, :details_json, CURRENT_TIMESTAMP
            )
            """
            for v in violations:
                details_str = (
                    json.dumps(v.get("details", {}))
                    if isinstance(v.get("details"), (dict, list))
                    else v.get("details")
                )
                payload = {
                    "rule_id": v["rule_id"],
                    "severity": v["severity"],
                    "person_pid": v["person_pid"],
                    "relative_pid": v.get("relative_pid"),
                    "description": v["description"],
                    "details_json": details_str,
                }
                conn.execute(sql, payload)

            return len(violations)

    def get_violations(
        self,
        root_pid: str | None = None,
        person_pid: str | None = None,
        severity: str | None = None,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves constraint violations with person, relative, and pedigree metadata."""
        query = """
        SELECT
            v.id,
            v.rule_id,
            v.severity,
            v.person_pid,
            p.name AS person_name,
            p.lifespan AS person_lifespan,
            v.relative_pid,
            rel_p.name AS relative_name,
            v.description,
            v.details_json,
            v.created_at,
            pt.generation,
            pt.ascendancy_number,
            pt.lineage_path,
            COALESCE(sc.confidence_score, 0.0) AS confidence_score,
            COALESCE(sc.confidence_level, 'UNSOURCED') AS confidence_level
        FROM constraint_violations v
        JOIN persons p ON v.person_pid = p.pid
        LEFT JOIN persons rel_p ON v.relative_pid = rel_p.pid
        LEFT JOIN pedigree_tree pt ON (v.person_pid = pt.person_pid AND (? IS NULL OR pt.root_pid = ?))
        LEFT JOIN person_audit_scores sc ON v.person_pid = sc.person_pid
        WHERE 1=1
        """
        params: list[Any] = [root_pid, root_pid]

        if person_pid:
            query += " AND v.person_pid = ?"
            params.append(person_pid)
        if severity:
            query += " AND v.severity = ?"
            params.append(severity.upper())
        if min_confidence is not None:
            query += " AND COALESCE(sc.confidence_score, 0.0) >= ?"
            params.append(min_confidence)

        query += " ORDER BY pt.generation ASC, pt.ascendancy_number ASC, v.severity ASC, v.rule_id ASC"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                if d.get("details_json"):
                    try:
                        d["details"] = json.loads(d["details_json"])
                    except Exception:
                        d["details"] = {}
                else:
                    d["details"] = {}
                results.append(d)
            return results

    def get_violations_summary(self, root_pid: str | None = None) -> dict[str, Any]:
        """Calculates aggregate statistics for constraint violations."""
        violations = self.get_violations(root_pid=root_pid)
        total = len(violations)
        severity_counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
        rule_counts: dict[str, int] = {}
        affected_persons = set()

        for v in violations:
            sev = v["severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            rule = v["rule_id"]
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
            affected_persons.add(v["person_pid"])

        return {
            "total_violations": total,
            "severity_counts": severity_counts,
            "rule_counts": rule_counts,
            "affected_person_count": len(affected_persons),
        }

