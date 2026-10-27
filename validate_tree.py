#!/usr/bin/env python3
"""CLI utility to validate biological and chronological constraints across pedigree trees."""

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

from src.constraints.engine import ConstraintEngine
from src.storage.db import Database

console = Console()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic Biological & Chronological Constraint Validator for Pedigree Trees."
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
        help="Root ancestor PID to validate ancestral subtree. If omitted, validates entire database graph.",
    )
    parser.add_argument(
        "--pid",
        type=str,
        default="",
        help="Validate a single specific individual PID.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Filter validation to ancestors with confidence score >= min-confidence (e.g. 70.0).",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist detected violations into SQLite constraint_violations table.",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        console.print(f"[bold red]Error:[/bold red] Database file '{args.db}' not found.")
        return 1

    db = Database(str(db_path))

    # Auto-detect root PID if none specified and no single PID specified
    target_root = args.root.strip()
    target_pid = args.pid.strip()

    if not target_root and not target_pid:
        # Check if there is an ingestion run or pedigree tree root
        with db.get_connection() as conn:
            row = conn.execute("SELECT root_pid FROM ingestion_runs ORDER BY id DESC LIMIT 1").fetchone()
            if row and row["root_pid"]:
                target_root = row["root_pid"]

    console.print("\n[bold]Genealogical Constraint & Biological Anomaly Validator[/bold]\n")

    filter_desc = []
    if target_root and not target_pid:
        filter_desc.append(f"[cyan]Subtree Root:[/cyan] [bold green]{target_root}[/bold green]")
    elif target_pid:
        filter_desc.append(f"[cyan]Single Person:[/cyan] [bold green]{target_pid}[/bold green]")
    else:
        filter_desc.append("[cyan]Scope:[/cyan] [bold green]Entire Graph[/bold green]")

    if args.min_confidence is not None:
        filter_desc.append(f"[cyan]Min Confidence Filter:[/cyan] [bold yellow]>={args.min_confidence:.1f}%[/bold yellow]")

    filter_desc.append(f"[cyan]Database:[/cyan] {args.db}")
    filter_desc.append(f"[cyan]Persist to DB:[/cyan] {'[green]Yes[/green]' if args.persist else '[dim]No[/dim]'}")

    console.print(Panel("\n".join(filter_desc), title="Validation Scope", border_style="blue"))

    # Execute Constraint Engine
    engine = ConstraintEngine(db)
    report = engine.validate(
        root_pid=target_root if not target_pid else None,
        person_pid=target_pid if target_pid else None,
        min_confidence=args.min_confidence,
        persist=args.persist,
    )

    # 1. Compliance Overview
    pass_color = "green" if report.pass_rate >= 95.0 else ("yellow" if report.pass_rate >= 80.0 else "red")
    summary_text = (
        f"[bold]Total Persons Evaluated:[/bold] {report.total_persons}\n"
        f"[bold]Total Relationships Evaluated:[/bold] {report.total_relationships}\n"
        f"[bold]Pedigree Biological Pass Rate:[/bold] [{pass_color}]{report.pass_rate:.1f}%[/{pass_color}]\n\n"
        f"[bold red]Critical Errors:[/bold red] {report.error_count}  |  "
        f"[bold yellow]Warnings / Outliers:[/bold yellow] {report.warning_count}  |  "
        f"[bold cyan]Informational / Posthumous:[/bold cyan] {report.info_count}\n\n"
    )

    if report.violations_by_rule:
        summary_text += "[bold]Violations by Rule:[/bold]\n"
        for rule, count in sorted(report.violations_by_rule.items()):
            summary_text += f" • [cyan]{rule}[/cyan]: {count}\n"
    else:
        summary_text += "[bold green]✓ No biological or chronological violations detected![/bold green]\n"

    console.print(
        Panel(
            summary_text,
            title="Validation Summary & Compliance",
            border_style="green" if report.error_count == 0 else "red",
        )
    )

    # 2. Detailed Violations Table
    if report.violations:
        table = Table(title="Detected Violations & Anomalies", border_style="yellow")
        table.add_column("Severity", justify="center", style="bold")
        table.add_column("Rule ID", style="bold cyan")
        table.add_column("Person PID / Name", style="white")
        table.add_column("Relative", style="dim")
        table.add_column("Deficit / Violation Description", style="white")

        # Map person names for nicer display
        with db.get_connection() as conn:
            all_pids = set()
            for v in report.violations:
                all_pids.add(v.person_pid)
                if v.relative_pid:
                    all_pids.add(v.relative_pid)
            placeholders = ",".join("?" for _ in all_pids)
            p_rows = conn.execute(f"SELECT pid, name, lifespan FROM persons WHERE pid IN ({placeholders})", list(all_pids)).fetchall()
            p_info = {r["pid"]: f"{r['name']} ({r['pid']})" for r in p_rows}

        for v in report.violations:
            if v.severity == "ERROR":
                sev_styled = "[bold red]ERROR[/bold red]"
            elif v.severity == "WARNING":
                sev_styled = "[bold yellow]WARN[/bold yellow]"
            else:
                sev_styled = "[bold cyan]INFO[/bold cyan]"

            person_label = p_info.get(v.person_pid, v.person_pid)
            rel_label = p_info.get(v.relative_pid, v.relative_pid or "—")

            table.add_row(
                sev_styled,
                v.rule_id,
                person_label,
                rel_label,
                v.description,
            )

        console.print(table)
    else:
        console.print(
            Panel(
                "[bold green]✓ 100% Deterministic Compliance:[/bold green] All assessed individuals, "
                "parent-child generations, and marriages satisfy chronological and biological laws.",
                border_style="green",
            )
        )

    if args.persist:
        console.print(f"[dim]Persisted {len(report.violations)} violation records into table 'constraint_violations'.[/dim]\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
