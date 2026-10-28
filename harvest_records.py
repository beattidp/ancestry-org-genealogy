#!/usr/bin/env python3
"""CLI utility to harvest external historical records, passenger lists, and newspapers."""

import argparse
import sys
from pathlib import Path
from typing import Any

from src.storage.db import Database
from src.sources import (
    CandidateDiscovery,
    ChroniclingAmericaHarvester,
    InternetArchiveHarvester,
)


def format_table_row(cols: list[str], widths: list[int]) -> str:
    """Formats a single row with padding."""
    return " | ".join(c.ljust(w)[:w] for c, w in zip(cols, widths))


def harvest_for_person(
    db: Database,
    person: dict[str, Any],
    harvesters: list[Any],
    limit_per_harvester: int = 5,
    min_score: float = 0.20,
) -> list[CandidateDiscovery]:
    """Harvests candidate discoveries for a single person across harvesters."""
    with db.get_connection() as conn:
        facts = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM facts WHERE person_pid = ?", (person["pid"],)
            ).fetchall()
        ]

    saved_discoveries: list[CandidateDiscovery] = []
    for h in harvesters:
        print(f"  -> Querying {h.name}...", end=" ", flush=True)
        try:
            results = h.search_person(person, facts=facts, limit=limit_per_harvester)
            filtered = [r for r in results if r.confidence_score >= min_score]
            print(f"found {len(results)} hits ({len(filtered)} above score {min_score:.2f})")
            for disc in filtered:
                db.upsert_candidate_discovery(disc.to_dict())
                saved_discoveries.append(disc)
        except Exception as e:
            print(f"failed ({e})")

    return saved_discoveries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harvest historical newspapers, passenger manifests, and digitized genealogies."
    )
    parser.add_argument(
        "--harvester",
        choices=["newspaper", "archive", "all"],
        default="all",
        help="Select harvester: newspaper (Library of Congress), archive (Internet Archive), or all.",
    )
    parser.add_argument(
        "--target",
        choices=["brick_walls", "unsourced", "pid"],
        default="brick_walls",
        help="Target cohort to harvest: brick_walls (0 parents), unsourced, or specific PID.",
    )
    parser.add_argument(
        "--pid",
        type=str,
        help="Target person PID (required if --target pid).",
    )
    parser.add_argument(
        "--max-gen",
        type=int,
        default=5,
        help="Maximum pedigree generation to target (default: 5).",
    )
    parser.add_argument(
        "--person-limit",
        type=int,
        default=10,
        help="Maximum number of persons to process in this run (default: 10).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum candidate records to retrieve per harvester per person (default: 5).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.20,
        help="Minimum confidence score threshold to persist candidates (default: 0.20).",
    )
    parser.add_argument(
        "--export-markdown",
        type=str,
        help="Path to export formatted candidate discovery report.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display current candidate discovery summary in database and exit.",
    )
    parser.add_argument(
        "--list-candidates",
        action="store_true",
        help="List candidate discoveries from the database and exit.",
    )
    parser.add_argument(
        "--status",
        choices=["all", "pending", "confirmed", "rejected"],
        default="pending",
        help="Filter status for --list-candidates (default: pending).",
    )
    parser.add_argument(
        "--confirm",
        type=int,
        metavar="ID",
        help="Confirm candidate discovery ID and promote it to a verified source in SQLite.",
    )
    parser.add_argument(
        "--reject",
        type=int,
        metavar="ID",
        help="Reject candidate discovery ID (mark as rejected).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to SQLite pedigree database.",
    )

    args = parser.parse_args()
    db = Database(args.db_path)

    # 1. Handle Confirm
    if args.confirm is not None:
        cand = db.get_candidate_by_id(args.confirm)
        if not cand:
            print(f"Error: Candidate discovery ID {args.confirm} not found.", file=sys.stderr)
            sys.exit(1)
        res = db.promote_candidate_to_source(args.confirm)
        if res:
            source_id, person_source_id = res
            print("\n[SUCCESS] Confirmed and promoted candidate discovery:")
            print(f"  ID:          {args.confirm}")
            print(f"  Person:      {cand.get('person_name')} ({cand['person_pid']})")
            print(f"  Title:       {cand['title']}")
            print(f"  Source ID:   {source_id}")
            print(f"  Link ID:     {person_source_id}")
            print(f"  Status:      CONFIRMED\n")
        else:
            print(f"Failed to promote candidate ID {args.confirm}.", file=sys.stderr)
        sys.exit(0)

    # 2. Handle Reject
    if args.reject is not None:
        cand = db.get_candidate_by_id(args.reject)
        if not cand:
            print(f"Error: Candidate discovery ID {args.reject} not found.", file=sys.stderr)
            sys.exit(1)
        ok = db.update_candidate_status(args.reject, "rejected")
        if ok:
            print(f"\n[REJECTED] Candidate ID {args.reject} ({cand['title'][:40]}) marked as REJECTED.\n")
        else:
            print(f"Failed to update candidate ID {args.reject}.", file=sys.stderr)
        sys.exit(0)

    # 3. Handle Summary
    if args.summary:
        summary = db.get_discovery_summary()
        print("\n==================================================")
        print(" Candidate Discovery Summary")
        print("==================================================")
        print(f"Total Discoveries:   {summary['total_discoveries']}")
        print(f"Distinct Persons:    {summary['distinct_persons']}")
        print(f"Average Confidence:  {summary['average_confidence']:.1%}")
        print("\nBy Harvester:")
        for h, count in summary["harvester_counts"].items():
            print(f"  - {h:22}: {count}")
        print("\nBy Discovery Type:")
        for t, count in summary["type_counts"].items():
            print(f"  - {t:22}: {count}")
        print("\nBy Status:")
        for s, count in summary["status_counts"].items():
            print(f"  - {s:22}: {count}")
        print("==================================================\n")
        sys.exit(0)

    # 4. Handle List Candidates
    if args.list_candidates:
        filter_status = None if args.status == "all" else args.status
        discoveries = db.get_candidate_discoveries(
            person_pid=args.pid,
            status=filter_status,
            min_confidence=args.min_score,
            limit=args.person_limit * 5,
        )
        print("\n" + "=" * 115)
        print(f" CANDIDATE DISCOVERIES (Status: {args.status.upper()}, Total: {len(discoveries)})")
        print("=" * 115)
        if not discoveries:
            print("No candidate records found matching criteria.\n")
            sys.exit(0)
        headers = ["ID", "PID", "Ancestor Name", "Type", "Conf", "Status", "Title"]
        widths = [5, 8, 20, 16, 6, 10, 40]
        print(format_table_row(headers, widths))
        print("-" * 115)
        for cand in discoveries:
            cols = [
                str(cand["id"]),
                cand["person_pid"],
                (cand.get("person_name") or "Unknown")[:19],
                cand["discovery_type"][:15],
                f"{cand['confidence_score']:.0%}",
                cand["status"].upper(),
                cand["title"][:38],
            ]
            print(format_table_row(cols, widths))
            print(f"     URL:   {cand['url']}")
            print(f"     Match: {cand.get('relevance_reason')}")
            print("-" * 115)
        sys.exit(0)

    # Initialize harvesters
    harvester_instances = []
    if args.harvester in ("newspaper", "all"):
        harvester_instances.append(ChroniclingAmericaHarvester())
    if args.harvester in ("archive", "all"):
        harvester_instances.append(InternetArchiveHarvester())

    # Resolve target persons
    target_persons: list[dict[str, Any]] = []

    if args.target == "pid":
        if not args.pid:
            print("Error: --pid is required when --target pid is specified.", file=sys.stderr)
            sys.exit(1)
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM persons WHERE pid = ?", (args.pid,)).fetchone()
            if not row:
                print(f"Error: Person PID {args.pid} not found in database.", file=sys.stderr)
                sys.exit(1)
            target_persons.append(dict(row))

    elif args.target == "brick_walls":
        brick_walls = db.get_terminal_brick_walls(max_generation=args.max_gen)
        # Filter living if needed
        target_persons = [b for b in brick_walls if "Living" not in (b.get("lifespan") or "")][:args.person_limit]

    elif args.target == "unsourced":
        with db.get_connection() as conn:
            query = """
            SELECT p.*, pt.generation, pt.ascendancy_number
            FROM pedigree_tree pt
            JOIN persons p ON pt.person_pid = p.pid
            LEFT JOIN person_audit_scores sc ON pt.person_pid = sc.person_pid
            WHERE COALESCE(sc.confidence_level, 'UNSOURCED') = 'UNSOURCED'
              AND pt.generation <= ?
              AND p.living = 0
            ORDER BY pt.generation ASC, pt.ascendancy_number ASC
            LIMIT ?
            """
            rows = conn.execute(query, (args.max_gen, args.person_limit)).fetchall()
            target_persons = [dict(r) for r in rows]

    if not target_persons:
        print("No target persons found matching criteria.")
        sys.exit(0)

    # Normalize PID key across different queries
    for p in target_persons:
        if "pid" not in p:
            p["pid"] = p.get("person_pid")

    print(f"\nTargeting {len(target_persons)} ancestors across Generations 1–{args.max_gen} for external harvesting.")
    print(f"Harvesters: {[h.name for h in harvester_instances]}\n")

    all_harvested: list[CandidateDiscovery] = []

    for idx, person in enumerate(target_persons, 1):
        print(f"[{idx}/{len(target_persons)}] {person.get('name')} ({person['pid']}) | {person.get('lifespan')} | {person.get('birth_place') or 'Unknown'}")
        discoveries = harvest_for_person(
            db=db,
            person=person,
            harvesters=harvester_instances,
            limit_per_harvester=args.limit,
            min_score=args.min_score,
        )
        all_harvested.extend(discoveries)

    # Print summary of discoveries
    print(f"\nHarvest complete. Discovered {len(all_harvested)} candidate records meeting min-score {args.min_score:.2f}.")

    all_stored = db.get_candidate_discoveries(min_confidence=args.min_score, limit=50)
    if all_stored:
        print("\n" + "=" * 115)
        print(" TOP CANDIDATE DISCOVERIES (Ranked by Match Confidence)")
        print("=" * 115)
        headers = ["PID", "Ancestor Name", "Harvester", "Type", "Date", "Conf", "Title / Record"]
        widths = [8, 20, 18, 16, 10, 6, 30]
        print(format_table_row(headers, widths))
        print("-" * 115)
        for cand in all_stored[:25]:
            cols = [
                cand["person_pid"],
                cand.get("person_name") or "Unknown",
                cand["harvester"],
                cand["discovery_type"],
                str(cand.get("date_str") or "Unknown"),
                f"{cand['confidence_score']:.0%}",
                cand["title"][:28],
            ]
            print(format_table_row(cols, widths))
            print(f"     URL:    {cand['url']}")
            print(f"     Match:  {cand.get('relevance_reason')}")
            if cand.get("snippet_text"):
                snip = cand["snippet_text"][:160].replace("\n", " ")
                print(f"     Snippet: {snip}...")
            print("-" * 115)

    if args.export_markdown:
        out_path = Path(args.export_markdown)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# Candidate External Record Discoveries\n\n")
            f.write(f"Generated across Generations 1–{args.max_gen} | Total Discoveries: {len(all_stored)}\n\n")
            f.write("| PID | Ancestor | Harvester | Type | Date | Match % | Title / Scan Link | Match Rationale |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for c in all_stored:
                link = f"[{c['title'][:40]}]({c['url']})" if c.get("url") else c["title"][:40]
                f.write(
                    f"| `{c['person_pid']}` | **{c.get('person_name', 'Unknown')}** "
                    f"| `{c['harvester']}` | `{c['discovery_type']}` | {c.get('date_str') or '-'} "
                    f"| **{c['confidence_score']:.0%}** | {link} | {c.get('relevance_reason', '')} |\n"
                )
        print(f"\nExported Markdown report to: {out_path}")


if __name__ == "__main__":
    main()
