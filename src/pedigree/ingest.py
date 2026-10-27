"""Pedigree ingestion engine connecting FamilySearch API to SQLite database."""

from dataclasses import dataclass, field
from typing import Any, Callable
from src.familysearch.client import FamilySearchClient
from src.pedigree.extractor import (
    calculate_generation_and_path,
    derive_pedigree_parent_child_relationships,
    extract_facts,
    extract_person,
    extract_relationships,
)
from src.storage.db import Database


@dataclass
class IngestionResult:
    """Summary metrics of an executed pedigree ingestion run."""

    root_pid: str
    max_generations: int
    total_persons: int
    total_relationships: int
    total_facts: int
    generations_found: dict[int, int] = field(default_factory=dict)
    run_id: int = 0
    status: str = "completed"


class PedigreeIngester:
    """Orchestrates fetching multi-generational ancestry from FamilySearch and storing locally."""

    def __init__(self, client: FamilySearchClient, db: Database) -> None:
        self.client = client
        self.db = db

    def ingest_ancestry(
        self,
        root_pid: str,
        max_generations: int = 4,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> IngestionResult:
        """Ingests multi-generational ancestry tree starting from root_pid."""
        run_id = self.db.start_ingestion_run(root_pid, max_generations)

        try:
            # Step 1: Initial query (FamilySearch API accepts up to 8 generations per call)
            initial_fetch_depth = min(max_generations, 8)
            if progress_callback:
                progress_callback(f"Querying FamilySearch for {initial_fetch_depth} generations...", 0, 100)

            data = self.client.get_ancestry(
                root_pid,
                generations=initial_fetch_depth,
                person_details=True,
                marriage_details=True,
            )

            persons_map: dict[str, dict[str, Any]] = {}
            pedigree_nodes: list[tuple[str, str, int, int | None, str]] = []
            facts_count = 0
            person_facts_map: dict[str, list[dict[str, Any]]] = {}

            raw_persons = data.get("persons", [])
            total_raw = len(raw_persons)

            for idx, raw_p in enumerate(raw_persons):
                person = extract_person(raw_p)
                pid = person["pid"]
                persons_map[pid] = person

                # Extract Ahnentafel / Ascendancy number
                display = raw_p.get("display", {})
                asc_raw = display.get("ascendancyNumber")
                asc_num: int | None = None
                if asc_raw is not None:
                    try:
                        asc_num = int(str(asc_raw).strip())
                    except ValueError:
                        asc_num = None

                if asc_num is not None and asc_num > 0:
                    gen, path = calculate_generation_and_path(asc_num)
                else:
                    gen, path = (0, "self") if pid == root_pid else (1, "unknown")

                pedigree_nodes.append((root_pid, pid, gen, asc_num, path))

                # Collect facts
                facts = extract_facts(raw_p)
                person_facts_map[pid] = facts
                facts_count += len(facts)

                if progress_callback:
                    progress_callback(f"Parsed person: {person['name']}", idx + 1, total_raw)

            # Step B: Insert all persons FIRST to satisfy foreign key constraints
            self.db.upsert_persons_batch(list(persons_map.values()))

            # Step C: Save pedigree nodes
            with self.db.get_connection() as conn:
                for r_pid, p_pid, gen, asc, path in pedigree_nodes:
                    self.db.upsert_pedigree_node(r_pid, p_pid, gen, asc, path, conn=conn)

            # Step D: Save facts for each person
            for pid, facts in person_facts_map.items():
                self.db.replace_facts(pid, facts)

            # Step E: Save relationships
            # 1. Explicit relationships from API (e.g. Couples with marriages)
            raw_rels = data.get("relationships", []) or data.get("childAndParentsRelationships", [])
            extracted_rels = extract_relationships(raw_rels)

            # 2. Derive parent-child relationships from Ahnentafel numbers
            asc_map = {asc: pid for _, pid, _, asc, _ in pedigree_nodes if asc is not None}
            derived_pc_rels = derive_pedigree_parent_child_relationships(asc_map)

            # Combine and batch upsert
            all_rels = extracted_rels + derived_pc_rels
            self.db.upsert_relationships_batch(all_rels)
            extracted_rels = all_rels

            # Step 2: Handle deep recursive ingestion if max_generations > 8
            if max_generations > 8:
                remaining_generations = max_generations - 8
                # Find leaf ancestors at generation 8
                leaf_nodes = [
                    (pid, asc) for _, pid, gen, asc, _ in pedigree_nodes if gen == 7 or gen == 8
                ]

                for leaf_pid, leaf_asc in leaf_nodes:
                    if not leaf_asc:
                        continue
                    try:
                        sub_data = self.client.get_ancestry(
                            leaf_pid,
                            generations=min(remaining_generations, 8),
                            person_details=True,
                            marriage_details=True,
                        )
                        sub_persons = sub_data.get("persons", [])
                        for sub_raw in sub_persons:
                            sub_pid = sub_raw.get("id")
                            if not sub_pid or sub_pid in persons_map:
                                continue

                            sub_person = extract_person(sub_raw)
                            persons_map[sub_pid] = sub_person
                            self.db.upsert_person(sub_person)

                            sub_asc_raw = sub_raw.get("display", {}).get("ascendancyNumber")
                            if sub_asc_raw:
                                try:
                                    sub_asc = int(str(sub_asc_raw).strip())
                                    if sub_asc > 1:
                                        # Compute global Ahnentafel
                                        sub_gen, _ = calculate_generation_and_path(sub_asc)
                                        global_asc = (leaf_asc << sub_gen) + (
                                            sub_asc - (1 << sub_gen)
                                        )
                                        global_gen, global_path = calculate_generation_and_path(
                                            global_asc
                                        )
                                        self.db.upsert_pedigree_node(
                                            root_pid,
                                            sub_pid,
                                            global_gen,
                                            global_asc,
                                            global_path,
                                        )
                                except ValueError:
                                    pass

                            sub_facts = extract_facts(sub_raw)
                            self.db.replace_facts(sub_pid, sub_facts)
                            facts_count += len(sub_facts)

                        sub_rels = extract_relationships(
                            sub_data.get("childAndParentsRelationships", [])
                        )
                        self.db.upsert_relationships_batch(sub_rels)
                        extracted_rels.extend(sub_rels)

                    except Exception:
                        # Continue with other branches if one deep leaf has no ancestry
                        continue

            # Calculate generation stats
            stats = self.db.get_pedigree_stats(root_pid)
            generations_found = {
                gen: data["count"] for gen, data in stats.get("generations", {}).items()
            }

            self.db.finish_ingestion_run(
                run_id=run_id,
                persons_count=len(persons_map),
                rels_count=len(extracted_rels),
                status="completed",
            )

            return IngestionResult(
                root_pid=root_pid,
                max_generations=max_generations,
                total_persons=len(persons_map),
                total_relationships=len(extracted_rels),
                total_facts=facts_count,
                generations_found=generations_found,
                run_id=run_id,
                status="completed",
            )

        except Exception as exc:
            self.db.finish_ingestion_run(
                run_id=run_id,
                persons_count=0,
                rels_count=0,
                status=f"failed: {exc}",
            )
            raise
