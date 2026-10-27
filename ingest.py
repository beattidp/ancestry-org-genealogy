#!/usr/bin/env python3
"""CLI utility to ingest FamilySearch ancestry trees into local SQLite database."""

import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.familysearch.auth import SessionManager
from src.familysearch.client import FamilySearchClient
from src.pedigree.ingest import PedigreeIngester
from src.storage.db import Database

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest FamilySearch ancestry pedigree into local SQLite database."
    )
    parser.add_argument(
        "--root",
        type=str,
        default="",
        help="Root Person PID (e.g. ABCD-123). If omitted, detects root PID from session.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=7,
        help="Number of base ancestor generations to ingest in single pass (default: 7).",
    )
    parser.add_argument(
        "--recursive-to",
        type=int,
        default=10,
        help="Target recursive depth to expand frontier leaf ancestors (default: 10, set 0 to disable).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/pedigree.sqlite",
        help="Path to SQLite database file (default: data/pedigree.sqlite).",
    )

    args = parser.parse_args()

    # Determine base and recursive targets
    base_generations = min(args.generations, 7)
    target_depth = max(args.generations, args.recursive_to) if args.recursive_to > 0 else args.generations

    console.print("\n[bold]FamilySearch Pedigree Ingestion Engine[/bold]\n")

    # Step 1: Validate Session
    settings = get_settings()
    session_mgr = SessionManager(settings)
    auth_status = session_mgr.validate_session()

    if not auth_status.is_valid:
        console.print(
            Panel(
                f"[bold red]Authentication Error:[/bold red] {auth_status.message}",
                title="[red]Invalid Session[/red]",
                border_style="red",
            )
        )
        return 1

    root_pid = args.root.strip() or auth_status.person_id
    if not root_pid:
        console.print("[red]Error:[/red] Could not determine root PID. Please specify --root <PID>.")
        return 1

    console.print(
        f"[cyan]Root Person PID:[/cyan] [bold green]{root_pid}[/bold green] "
        f"({auth_status.display_name or 'Current User'})\n"
        f"[cyan]Base Generations (Pass 1):[/cyan] [bold]{base_generations}[/bold]\n"
        f"[cyan]Recursive Frontier Target (Pass 2):[/cyan] [bold]{target_depth}[/bold]\n"
        f"[cyan]Target Database:[/cyan] [bold]{args.db}[/bold]\n"
    )

    db = Database(args.db)
    client = FamilySearchClient(session_mgr, settings)
    ingester = PedigreeIngester(client, db)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Ingesting ancestry...", total=100)

        def on_progress(desc: str, current: int, total: int) -> None:
            pct = int((current / total) * 100) if total > 0 else 0
            progress.update(task, description=f"[cyan]{desc}", completed=pct)

        try:
            result = ingester.ingest_ancestry(
                root_pid=root_pid,
                max_generations=base_generations,
                recursive_to=target_depth,
                progress_callback=on_progress,
            )
            progress.update(task, description="[bold green]Ingestion complete!", completed=100)
        except Exception as exc:
            console.print(f"\n[bold red]Ingestion Failed:[/bold red] {exc}")
            return 2

    # Render Summary Table
    table = Table(title="Pedigree Ingestion Results", border_style="green")
    table.add_column("Generation", style="bold cyan")
    table.add_column("Relationship Label", style="white")
    table.add_column("Expected Max", justify="right", style="dim")
    table.add_column("Found in Tree", justify="right", style="bold green")
    table.add_column("Coverage", justify="right")

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

    stats = db.get_pedigree_stats(root_pid)
    for gen, gen_data in sorted(stats["generations"].items()):
        label = gen_labels.get(gen, f"{gen-2}th Great-Grandparents")
        expected = gen_data["expected"]
        found = gen_data["count"]
        pct = gen_data["completeness"]
        table.add_row(
            str(gen),
            label,
            str(expected),
            str(found),
            f"{pct:.1f}%",
        )

    console.print(table)

    console.print(
        Panel(
            f"[bold green]✓ Successfully persisted {result.total_persons} ancestors, "
            f"{result.total_relationships} relationships, and {result.total_facts} facts.[/bold green]\n\n"
            f"Database file: [italic]{args.db}[/italic]\n"
            f"Run [bold cyan]python tree_summary.py --db {args.db}[/bold cyan] to inspect offline.",
            title="[bold green]Pedigree Ingestion Complete[/bold green]",
            border_style="green",
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
