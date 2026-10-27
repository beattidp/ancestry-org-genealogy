#!/usr/bin/env python3
"""Offline inspection and analysis utility for local genealogy SQLite database."""

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.db import Database

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and summarize local pedigree SQLite database."
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to SQLite database file (default: data/pedigree.sqlite).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default="",
        help="Root Person PID to summarize. If omitted, uses the first root PID in database.",
    )

    args = parser.parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database file not found at [italic]{db_path}[/italic].")
        console.print("Run [bold cyan]python ingest.py[/bold cyan] first to download your pedigree.")
        return 1

    db = Database(db_path)

    # Determine root PID if not provided
    root_pid = args.root.strip()
    if not root_pid:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT root_pid FROM pedigree_tree ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            if row:
                root_pid = row["root_pid"]

    if not root_pid:
        console.print("[yellow]Database is empty. No pedigree tree records found.[/yellow]")
        return 0

    root_person = db.get_person(root_pid)
    root_name = root_person["name"] if root_person else "Unknown"

    console.print(
        Panel(
            f"[bold]Root Person:[/bold] {root_name} ([cyan]{root_pid}[/cyan])\n"
            f"[bold]Database:[/bold] [italic]{args.db}[/italic]",
            title="[bold green]Local Pedigree Summary[/bold green]",
            border_style="green",
        )
    )

    # Table 1: Generational Coverage
    stats = db.get_pedigree_stats(root_pid)
    table_stats = Table(title="Generational Coverage", border_style="cyan")
    table_stats.add_column("Gen", justify="center", style="bold")
    table_stats.add_column("Relationship", style="white")
    table_stats.add_column("Expected Max", justify="right", style="dim")
    table_stats.add_column("Found in Tree", justify="right", style="bold green")
    table_stats.add_column("Coverage", justify="right")

    gen_labels = {
        0: "Self",
        1: "Parents",
        2: "Grandparents",
        3: "1st Great-Grandparents",
        4: "2nd Great-Grandparents",
        5: "3rd Great-Grandparents",
        6: "4th Great-Grandparents",
        7: "5th Great-Grandparents",
        8: "6th Great-Grandparents",
        9: "7th Great-Grandparents",
        10: "8th Great-Grandparents",
        11: "9th Great-Grandparents",
        12: "10th Great-Grandparents",
        13: "11th Great-Grandparents",
        14: "12th Great-Grandparents",
        15: "13th Great-Grandparents",
    }

    for gen, gen_data in sorted(stats["generations"].items()):
        label = gen_labels.get(gen, f"{gen-2}th Great-Grandparents")
        expected = gen_data["expected"]
        found = gen_data["count"]
        pct = gen_data["completeness"]
        table_stats.add_row(
            str(gen),
            label,
            str(expected),
            str(found),
            f"{pct:.1f}%",
        )

    console.print(table_stats)

    # Table 2: Identified Pedigree Gaps / Brick Walls
    max_gap_gen = max(stats["generations"].keys()) if stats["generations"] else 5
    gaps = db.get_pedigree_gaps(root_pid, max_generation=min(max_gap_gen, 7))
    if gaps:
        table_gaps = Table(
            title="Identified Pedigree Gaps (Target Lines for Primary Research)",
            border_style="yellow",
        )
        table_gaps.add_column("Gen", justify="center")
        table_gaps.add_column("Ahnen #", justify="center", style="dim")
        table_gaps.add_column("Ancestor Name", style="bold")
        table_gaps.add_column("PID", style="cyan")
        table_gaps.add_column("Missing Relationship", style="bold yellow")

        for gap in gaps[:15]:  # limit to first 15 for readability
            table_gaps.add_row(
                str(gap["generation"]),
                str(gap["ascendancy_number"] or "-"),
                gap["name"],
                gap["pid"],
                " & ".join(gap["missing"]),
            )

        console.print(table_gaps)
        if len(gaps) > 15:
            console.print(f"[dim]... and {len(gaps) - 15} more ancestors with missing parents.[/dim]")

    # Table 3: Earliest Documented Ancestors
    with db.get_connection() as conn:
        earliest_rows = conn.execute(
            """
            SELECT pt.generation, pt.ascendancy_number, p.name, p.pid, p.birth_date, p.birth_place
            FROM pedigree_tree pt
            JOIN persons p ON pt.person_pid = p.pid
            WHERE pt.root_pid = ? AND p.birth_date != ''
            ORDER BY p.birth_date ASC
            LIMIT 5;
            """,
            (root_pid,),
        ).fetchall()

    if earliest_rows:
        table_earliest = Table(title="Earliest Documented Ancestors", border_style="magenta")
        table_earliest.add_column("Gen", justify="center")
        table_earliest.add_column("Ancestor Name", style="bold")
        table_earliest.add_column("PID", style="cyan")
        table_earliest.add_column("Birth Date", style="green")
        table_earliest.add_column("Birth Place", style="white")

        for r in earliest_rows:
            table_earliest.add_row(
                str(r["generation"]),
                r["name"],
                r["pid"],
                r["birth_date"],
                r["birth_place"] or "Unknown",
            )

        console.print(table_earliest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
