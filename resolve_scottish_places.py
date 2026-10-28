#!/usr/bin/env python3
"""CLI utility to resolve archaic Scottish birth and death locations to official NRS civil parishes."""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from src.geo import ScottishGazetteer
from src.storage.db import Database


def format_table_row(cols: list[str], widths: list[int]) -> str:
    """Formats a single row with padding."""
    return " | ".join(c.ljust(w)[:w] for c, w in zip(cols, widths))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve Scottish pedigree locations to official NRS civil parishes and registration districts."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to SQLite pedigree database (default: data/pedigree.sqlite).",
    )
    parser.add_argument(
        "--export-markdown",
        type=str,
        default="doc/reports/scottish_ancestors_resolved.md",
        help="Path to export Markdown report (default: doc/reports/scottish_ancestors_resolved.md).",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: Database '{db_path}' not found.", file=sys.stderr)
        sys.exit(1)

    db = Database(db_path=db_path)
    gazetteer = ScottishGazetteer()

    print("==================================================")
    print(" Scottish Civil Parish & NRS Gazetteer Resolver")
    print("==================================================")
    print(f"Source Database: {db_path}\n")

    with db.get_connection() as conn:
        persons = conn.execute(
            """
            SELECT p.pid, p.name, p.lifespan, p.birth_date, p.birth_place, p.death_date, p.death_place,
                   pt.generation, pt.ascendancy_number
            FROM persons p
            LEFT JOIN pedigree_tree pt ON p.pid = pt.person_pid
            WHERE p.birth_place LIKE '%Scotland%' OR p.death_place LIKE '%Scotland%'
               OR p.birth_place LIKE '%Midlothian%' OR p.birth_place LIKE '%Argyll%'
               OR p.birth_place LIKE '%Aberdeen%' OR p.birth_place LIKE '%Peebles%'
            ORDER BY pt.generation ASC, p.name ASC
            """
        ).fetchall()

    resolved_records: list[dict[str, Any]] = []

    for r in persons:
        p = dict(r)
        # Check birth place
        if gazetteer.is_scottish_place(p.get("birth_place")):
            parish, county = gazetteer.resolve_place(p.get("birth_place"))
            resolved_records.append({
                "pid": p["pid"],
                "name": p.get("name") or "Unknown",
                "lifespan": p.get("lifespan") or "Unknown",
                "generation": p.get("generation"),
                "event_type": "Birth",
                "event_date": p.get("birth_date") or "-",
                "raw_place": p.get("birth_place") or "",
                "parish": parish,
                "county": county or (parish.county if parish else "Scotland"),
            })

        # Check death place
        if gazetteer.is_scottish_place(p.get("death_place")):
            parish, county = gazetteer.resolve_place(p.get("death_place"))
            resolved_records.append({
                "pid": p["pid"],
                "name": p.get("name") or "Unknown",
                "lifespan": p.get("lifespan") or "Unknown",
                "generation": p.get("generation"),
                "event_type": "Death",
                "event_date": p.get("death_date") or "-",
                "raw_place": p.get("death_place") or "",
                "parish": parish,
                "county": county or (parish.county if parish else "Scotland"),
            })

    print(f"Identified {len(resolved_records)} Scottish vital events across {len(persons)} ancestors.")
    print("-" * 115)
    headers = ["PID", "Ancestor Name", "Gen", "Event", "Raw Location", "NRS Parish / County"]
    widths = [8, 22, 4, 6, 32, 35]
    print(format_table_row(headers, widths))
    print("-" * 115)

    for rec in resolved_records:
        if rec["parish"]:
            parish_desc = f"{rec['parish'].parish_name} (#{rec['parish'].parish_number}, {rec['parish'].county})"
        elif rec["county"]:
            parish_desc = f"[County Level] {rec['county']}"
        else:
            parish_desc = "[Unresolved] Scotland General"

        cols = [
            rec["pid"],
            rec["name"][:21],
            str(rec.get("generation") if rec.get("generation") is not None else "-"),
            rec["event_type"],
            rec["raw_place"][:31],
            parish_desc[:34],
        ]
        print(format_table_row(cols, widths))

    print("-" * 115)

    if args.export_markdown:
        out_path = Path(args.export_markdown)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("# Resolved Scottish Ancestral Locations & NRS Civil Parishes\n\n")
            f.write(f"Generated from `data/pedigree.sqlite` | Total Scottish Events: {len(resolved_records)}\n\n")
            f.write("| PID | Ancestor | Gen | Event | Date | Raw Recorded Place | Resolved NRS Civil Parish | Historical County | ScotlandsPeople OPR Link |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for rec in resolved_records:
                name_tokens = rec["name"].split()
                surn = name_tokens[-1] if len(name_tokens) > 1 else rec["name"]
                givn = name_tokens[0] if name_tokens else ""
                year_num = None
                if rec["event_date"]:
                    m = re.search(r"\b(1[5-9]\d{2})\b", rec["event_date"])
                    if m:
                        year_num = int(m.group(1))

                if rec["parish"]:
                    parish_str = f"**{rec['parish'].parish_name}** (`{rec['parish'].parish_number}`)"
                    county_str = rec["parish"].county
                    link = f"[Search OPR]({rec['parish'].generate_scotlandspeople_url(surn, givn, year_num)})"
                elif rec["county"]:
                    parish_str = "*County-level jurisdiction*"
                    county_str = rec["county"]
                    link = "-"
                else:
                    parish_str = "*National jurisdiction*"
                    county_str = "Scotland"
                    link = "-"

                f.write(
                    f"| `{rec['pid']}` | **{rec['name']}** | {rec.get('generation') or '-'} | {rec['event_type']} "
                    f"| {rec['event_date']} | {rec['raw_place']} | {parish_str} | {county_str} | {link} |\n"
                )
        print(f"\nExported Markdown gazetteer report to: {out_path.resolve()}\n")


if __name__ == "__main__":
    main()
