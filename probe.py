#!/usr/bin/env python3
"""Connection and credential probe utility for FamilySearch Platform API."""

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ENV_PATH, get_settings
from src.familysearch.auth import SessionManager
from src.familysearch.client import FamilySearchClient

console = Console()


def show_setup_instructions() -> None:
    """Displays user guidance for setting up .env."""
    instructions = (
        "[bold cyan]How to Set Up Your FamilySearch Credentials:[/bold cyan]\n\n"
        "1. Create your local [bold].env[/bold] file by copying the template:\n"
        "   [yellow]cp .env.example .env[/yellow]\n\n"
        "2. Log in to [link=https://www.familysearch.org]https://www.familysearch.org[/link] in your browser.\n\n"
        "3. Open Developer Tools ([bold]F12[/bold] or [bold]Ctrl+Shift+I[/bold] / [bold]Cmd+Option+I[/bold]).\n\n"
        "4. Go to [bold]Application[/bold] (Chrome/Edge) or [bold]Storage[/bold] (Firefox) tab.\n\n"
        "5. Expand [bold]Cookies[/bold] -> [bold]https://www.familysearch.org[/bold].\n\n"
        "6. Copy the value of the [bold green]fssessionid[/bold green] cookie.\n\n"
        "7. Open [bold].env[/bold] and paste it into:\n"
        "   [yellow]FAMILYSEARCH_SESSION_ID=\"<your_token_here>\"[/yellow]\n"
    )
    console.print(Panel(instructions, title="[bold yellow]Credentials Needed[/bold yellow]", border_style="yellow"))


def main() -> int:
    console.print("\n[bold]FamilySearch Research Engine — Credential & API Probe[/bold]\n")

    if not ENV_PATH.exists():
        console.print(f"[yellow]Notice:[/yellow] [bold].env[/bold] file not found at [italic]{ENV_PATH}[/italic].")
        show_setup_instructions()
        return 1

    settings = get_settings()

    if not settings.familysearch_session_id.strip():
        console.print("[yellow]Notice:[/yellow] [bold]FAMILYSEARCH_SESSION_ID[/bold] in [italic].env[/italic] is empty.")
        show_setup_instructions()
        return 1

    console.print("[cyan]Probing FamilySearch API identity endpoint...[/cyan]")
    session_mgr = SessionManager(settings)
    auth_status = session_mgr.validate_session()

    if not auth_status.is_valid:
        error_panel = (
            f"[bold red]Connection Failed (Status {auth_status.status_code})[/bold red]\n\n"
            f"{auth_status.message}\n"
        )
        console.print(Panel(error_panel, title="[bold red]Authentication Error[/bold red]", border_style="red"))
        show_setup_instructions()
        return 2

    # Success Table
    table = Table(title="FamilySearch Authenticated Session Details", border_style="green")
    table.add_column("Property", style="bold cyan", width=22)
    table.add_column("Value", style="white")

    table.add_row("API Environment", settings.familysearch_env.upper())
    table.add_row("Base URL", settings.base_url)
    table.add_row("User ID", auth_status.user_id or "N/A")
    table.add_row("Display Name", auth_status.display_name or "N/A")
    table.add_row("Contact Name", auth_status.contact_name or "N/A")
    table.add_row("Tree Person ID (Root)", auth_status.person_id or "N/A")

    console.print(table)

    # Optional root person probe
    if auth_status.person_id:
        try:
            client = FamilySearchClient(session_mgr, settings)
            person_data = client.get_person(auth_status.person_id)
            persons = person_data.get("persons", [])
            if persons:
                root_person = persons[0]
                display = root_person.get("display", {})
                name = display.get("name", "Unknown")
                gender = display.get("gender", "Unknown")
                lifespan = display.get("lifespan", "Unknown")
                console.print(
                    Panel(
                        f"[bold]Root Person in Tree:[/bold] {name} ({gender}) - {lifespan}\n"
                        f"[bold]PID:[/bold] {auth_status.person_id}\n"
                        f"[green]✓ Tree read access verified successfully.[/green]",
                        title="[bold green]Tree Profile Verified[/bold green]",
                        border_style="green",
                    )
                )
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not fetch root person details: {exc}[/yellow]")

    console.print(
        Panel(
            "[bold green]✓ FamilySearch API connection active and verified![/bold green]\n"
            "You are ready to begin programmatic research and pedigree analysis.",
            border_style="green",
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
