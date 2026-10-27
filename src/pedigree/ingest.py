import time
from dataclasses import dataclass, field
from typing import Any, Callable
from src.familysearch.client import FamilySearchClient
from src.pedigree.extractor import (
    calculate_generation_and_path,
    calculate_global_ahnentafel,
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
        max_generations: int = 7,
        recursive_to: int = 10,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> IngestionResult:
        """Ingests multi-generational ancestry tree starting from root_pid with recursive frontier expansion."""
        target_max_gen = max(max_generations, recursive_to) if recursive_to > 0 else max_generations
        run_id = self.db.start_ingestion_run(root_pid, target_max_gen)

        try:
            # Step 1: Base Platform Ingestion (up to 7 generations in single call)
            initial_fetch_depth = min(max_generations, 7)
            if progress_callback:
                progress_callback(f"Querying FamilySearch for base {initial_fetch_depth} generations...", 0, 100)

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
            raw_rels = data.get("relationships", []) or data.get("childAndParentsRelationships", [])
            extracted_rels = extract_relationships(raw_rels)

            # Derive parent-child relationships from Ahnentafel numbers
            asc_map = {asc: pid for _, pid, _, asc, _ in pedigree_nodes if asc is not None}
            derived_pc_rels = derive_pedigree_parent_child_relationships(asc_map)

            # Combine and batch upsert
            all_rels = extracted_rels + derived_pc_rels
            self.db.upsert_relationships_batch(all_rels)
            extracted_rels = all_rels

            # Step 2: Recursive Frontier Expansion (up to target_max_gen)
            if target_max_gen > initial_fetch_depth:
                while True:
                    curr_pedigree = self.db.get_pedigree(root_pid)
                    if not curr_pedigree:
                        break

                    current_max_gen = max(p["generation"] for p in curr_pedigree)
                    if current_max_gen < initial_fetch_depth or current_max_gen >= target_max_gen:
                        break

                    # Identify frontier leaf ancestors at current_max_gen
                    leaf_nodes = [
                        (p["pid"], p["ascendancy_number"])
                        for p in curr_pedigree
                        if p["generation"] == current_max_gen and p["ascendancy_number"]
                    ]

                    if not leaf_nodes:
                        break

                    remaining_depth = min(target_max_gen - current_max_gen, 8)
                    total_leaves = len(leaf_nodes)
                    new_ancestors_found = 0

                    for leaf_idx, (leaf_pid, leaf_asc) in enumerate(leaf_nodes):
                        if progress_callback:
                            progress_callback(
                                f"Expanding Gen {current_max_gen} frontier [{leaf_idx + 1}/{total_leaves}]: PID {leaf_pid}...",
                                leaf_idx + 1,
                                total_leaves,
                            )

                        try:
                            sub_data = self.client.get_ancestry(
                                leaf_pid,
                                generations=remaining_depth,
                                person_details=True,
                                marriage_details=True,
                            )
                            sub_persons = sub_data.get("persons", [])
                            if not sub_persons:
                                continue

                            sub_asc_map: dict[int, str] = {}
                            sub_person_models = []
                            sub_pedigree_nodes = []
                            sub_facts_by_pid = {}

                            for sub_raw in sub_persons:
                                sub_pid = sub_raw.get("id")
                                if not sub_pid:
                                    continue

                                sub_person = extract_person(sub_raw)
                                if sub_pid not in persons_map:
                                    persons_map[sub_pid] = sub_person
                                    sub_person_models.append(sub_person)

                                sub_asc_raw = sub_raw.get("display", {}).get("ascendancyNumber")
                                if sub_asc_raw:
                                    try:
                                        sub_asc = int(str(sub_asc_raw).strip())
                                        sub_asc_map[sub_asc] = sub_pid
                                        if sub_asc > 1:
                                            # Calculate global Ahnentafel, generation, and path
                                            global_gen, global_asc, global_path = calculate_global_ahnentafel(
                                                leaf_asc, sub_asc
                                            )
                                            sub_pedigree_nodes.append(
                                                (root_pid, sub_pid, global_gen, global_asc, global_path)
                                            )
                                            new_ancestors_found += 1
                                    except ValueError:
                                        pass

                                sub_facts = extract_facts(sub_raw)
                                sub_facts_by_pid[sub_pid] = sub_facts
                                facts_count += len(sub_facts)

                            # Insert sub-persons first
                            if sub_person_models:
                                self.db.upsert_persons_batch(sub_person_models)

                            # Insert sub-pedigree nodes
                            if sub_pedigree_nodes:
                                with self.db.get_connection() as conn:
                                    for r_pid, p_pid, gen, asc, path in sub_pedigree_nodes:
                                        self.db.upsert_pedigree_node(r_pid, p_pid, gen, asc, path, conn=conn)

                            # Save sub-facts
                            for sp_pid, s_facts in sub_facts_by_pid.items():
                                self.db.replace_facts(sp_pid, s_facts)

                            # Extract sub-relationships
                            sub_couples = extract_relationships(sub_data.get("relationships", []))
                            sub_derived_pc = derive_pedigree_parent_child_relationships(sub_asc_map)
                            sub_all_rels = sub_couples + sub_derived_pc

                            if sub_all_rels:
                                self.db.upsert_relationships_batch(sub_all_rels)
                                extracted_rels.extend(sub_all_rels)

                            # Polite pacing
                            time.sleep(0.05)

                        except Exception:
                            # Log error and continue with remaining leaves
                            continue

                    if new_ancestors_found == 0:
                        break

            # Calculate generation stats
            stats = self.db.get_pedigree_stats(root_pid)
            generations_found = {
                gen: data["count"] for gen, data in stats.get("generations", {}).items()
            }

            total_ancestors_count = stats.get("total_ancestors", len(persons_map))
            self.db.finish_ingestion_run(
                run_id=run_id,
                persons_count=total_ancestors_count,
                rels_count=len(extracted_rels),
                status="completed",
            )

            return IngestionResult(
                root_pid=root_pid,
                max_generations=target_max_gen,
                total_persons=total_ancestors_count,
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
