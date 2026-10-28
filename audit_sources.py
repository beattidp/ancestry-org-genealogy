#!/usr/bin/env python3
"""CLI utility to audit attached sources, evaluate evidence, and score pedigree confidence."""

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

from src.audit.auditor import SourceAuditor
from src.config import get_settings
from src.familysearch.auth import SessionManager
from src.familysearch.client import FamilySearchClient
from src.storage.db import Database

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit attached sources and calculate genealogical confidence scores."
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
        help="Root Person PID. If omitted, uses the first root PID in database.",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch latest attached sources from FamilySearch API before auditing.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-fetching sources from FamilySearch API even if already cached.",
    )
    parser.add_argument(
        "--min-gen",
        type=int,
        default=None,
        help="Minimum generation to audit (e.g. 11). If omitted, starts from generation 0.",
    )
    parser.add_argument(
        "--max-gen",
        type=int,
        default=None,
        help="Maximum generation to audit (e.g. 7 or 10). If omitted, audits all available.",
    )

    args = parser.parse_args()
    db_path = Path(args.db)

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database file not found at [italic]{db_path}[/italic].")
        console.print("Run [bold cyan]python ingest.py[/bold cyan] first.")
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

    fetch_mode_str = "[green]Live FamilySearch API Sync[/green]" if args.fetch else "[yellow]Offline Cached Data[/yellow]"
    if args.refresh:
        fetch_mode_str += " (Refresh All)"

    gen_range_str = ""
    if args.min_gen is not None or args.max_gen is not None:
        min_lbl = f"Gen {args.min_gen}" if args.min_gen is not None else "Gen 0"
        max_lbl = f"Gen {args.max_gen}" if args.max_gen is not None else "Max"
        gen_range_str = f"\n[bold]Generational Range:[/bold] {min_lbl} to {max_lbl}"

    console.print(
        Panel(
            f"[bold]Root Person:[/bold] {root_name} ([cyan]{root_pid}[/cyan])\n"
            f"[bold]Database:[/bold] [italic]{args.db}[/italic]\n"
            f"[bold]Fetch Mode:[/bold] {fetch_mode_str}"
            f"{gen_range_str}",
            title="[bold green]Genealogical Source & Citation Auditor[/bold green]",
            border_style="green",
        )
    )

    client = None
    if args.fetch:
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
        client = FamilySearchClient(session_mgr, settings)

    auditor = SourceAuditor(client, db)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Auditing pedigree...", total=100)

        def on_progress(desc: str, current: int, total: int) -> None:
            pct = int((current / total) * 100) if total > 0 else 0
            progress.update(task, description=f"[cyan]{desc}", completed=pct)

        try:
            auditor.audit_pedigree(
                root_pid,
                fetch=args.fetch,
                refresh=args.refresh,
                min_generation=args.min_gen,
                max_generation=args.max_gen,
                progress_callback=on_progress,
            )
            progress.update(task, description="[bold green]Audit complete!", completed=100)
        except Exception as exc:
            console.print(f"\n[bold red]Audit Failed:[/bold red] {exc}")
            return 2

    # Render Table 1: Confidence Distribution
    summary = db.get_audit_summary(root_pid, min_generation=args.min_gen, max_generation=args.max_gen)
    total_ancestors = summary["total_ancestors"]
    conf_counts = summary["confidence_levels"]

    table_conf = Table(title="Pedigree Evidence Confidence Distribution", border_style="cyan")
    table_conf.add_column("Confidence Level", style="bold")
    table_conf.add_column("Count", justify="right", style="white")
    table_conf.add_column("Share", justify="right")
    table_conf.add_column("GPS Assessment Standard", style="dim")

    level_styles = {
        "HIGH": ("[green]HIGH (80-100%)[/green]", "Primary Tier 1 proof for Birth, Death, & Parentage"),
        "MEDIUM": ("[yellow]MEDIUM (50-79%)[/yellow]", "Secondary or partial primary proof; missing 1 core event"),
        "LOW": ("[red]LOW (1-49%)[/red]", "Sparse documentation; unverified claims or user trees"),
        "UNSOURCED": ("[dim red]UNSOURCED (0%)[/dim red]", "Zero attached sources in database"),
    }

    for level, (styled_label, desc) in level_styles.items():
        cnt = conf_counts.get(level, 0)
        pct = (cnt / total_ancestors * 100) if total_ancestors > 0 else 0
        table_conf.add_row(styled_label, str(cnt), f"{pct:.1f}%", desc)

    console.print(table_conf)

    # Render Table 2: Generational Coverage Matrix
    table_gen = Table(title="Generational Evidence Verification Matrix", border_style="green")
    table_gen.add_column("Gen", justify="center", style="bold")
    table_gen.add_column("Relationship", style="white")
    table_gen.add_column("Count", justify="right")
    table_gen.add_column("Birth Verified", justify="right")
    table_gen.add_column("Death Verified", justify="right")
    table_gen.add_column("Parentage Verified", justify="right")
    table_gen.add_column("Avg Confidence", justify="right", style="bold green")

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

    for gen, g_data in sorted(summary.get("generations", {}).items()):
        cnt = g_data["count"]
        b_pct = (g_data["birth_verified"] / cnt * 100) if cnt > 0 else 0
        d_pct = (g_data["death_verified"] / cnt * 100) if cnt > 0 else 0
        p_pct = (g_data["parentage_verified"] / cnt * 100) if cnt > 0 else 0
        table_gen.add_row(
            str(gen),
            gen_labels.get(gen, f"Gen {gen}"),
            str(cnt),
            f"{b_pct:.0f}%",
            f"{d_pct:.0f}%",
            f"{p_pct:.0f}%",
            f"{g_data['avg_score']:.1f}%",
        )

    console.print(table_gen)

    # Render Table 3: Actionable Evidentiary Deficits (Backlog for Research)
    scores = db.get_audit_scores(root_pid, min_generation=args.min_gen, max_generation=args.max_gen)
    deficit_ancestors = [s for s in scores if s["confidence_level"] in ("LOW", "UNSOURCED") or not s["parentage_verified"]]

    if deficit_ancestors:
        table_deficits = Table(
            title="Priority Evidentiary Deficits (Target Lines for Primary Record Search)",
            border_style="yellow",
        )
        table_deficits.add_column("Gen", justify="center")
        table_deficits.add_column("Ancestor Name", style="bold")
        table_deficits.add_column("PID", style="cyan")
        table_deficits.add_column("Score", justify="right", style="bold yellow")
        table_deficits.add_column("Tier 1", justify="right")
        table_deficits.add_column("Evidentiary Deficits & Missing Proofs", style="white")

        for d in deficit_ancestors[:12]:
            issues_str = "; ".join(d["issues"][:2]) if d["issues"] else "Unverified"
            table_deficits.add_row(
                str(d["generation"]),
                d["name"],
                d["pid"],
                f"{d['confidence_score']:.0f}%",
                str(d["tier1_sources"]),
                issues_str,
            )

        console.print(table_deficits)
        if len(deficit_ancestors) > 12:
            console.print(
                f"[dim]... and {len(deficit_ancestors) - 12} more ancestors with evidentiary deficits.[/dim]"
            )

    console.print(
        Panel(
            f"[bold]Average Pedigree Confidence Score:[/bold] [bold green]{summary['avg_confidence']:.1f}%[/bold green]\n"
            f"Audited [bold]{total_ancestors}[/bold] ancestors across the tree.\n"
            "Use the Deficits table above to prioritize census and vital record searches for specific ancestors.",
            title="[bold green]Audit Summary[/bold green]",
            border_style="green",
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
