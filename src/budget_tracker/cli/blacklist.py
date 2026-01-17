from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from budget_tracker.cli.mapping import load_mapping, save_mapping
from budget_tracker.models.bank_mapping import BankMapping

console = Console()


def list_available_banks(banks_dir: Path) -> list[str]:
    """Get list of configured bank names."""
    if not banks_dir.exists():
        return []
    return sorted([f.stem for f in banks_dir.glob("*.yaml")])


def display_blacklist(mapping: BankMapping) -> None:
    """Display current blacklist keywords for a bank."""
    console.print(f"\n[bold]Blacklist for {mapping.bank_name}:[/bold]")

    if not mapping.blacklist_keywords:
        console.print("  [dim](empty)[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Keyword")

    for i, k in enumerate(mapping.blacklist_keywords, start=1):
        table.add_row(str(i), k)

    console.print(table)


def add_keyword(mapping: BankMapping, banks_dir: Path) -> None:
    """Add a keyword to the blacklist."""
    keyword = Prompt.ask("\nEnter keyword to add")

    if not keyword.strip():
        console.print("[yellow]No keyword entered[/yellow]")
        return

    keyword = keyword.strip()

    if keyword in mapping.blacklist_keywords:
        console.print(f"[yellow]Keyword '{keyword}' already in blacklist[/yellow]")
        return

    mapping.blacklist_keywords.append(keyword)
    save_mapping(mapping, banks_dir)
    console.print(f"[green]✓[/green] Added '{keyword}' to {mapping.bank_name} blacklist")


def remove_keyword(mapping: BankMapping, banks_dir: Path) -> None:
    """Remove a keyword from the blacklist."""
    if not mapping.blacklist_keywords:
        console.print("[yellow]Blacklist is empty, nothing to remove[/yellow]")
        return

    display_blacklist(mapping)

    choices = [str(i) for i in range(1, len(mapping.blacklist_keywords) + 1)]
    choice = Prompt.ask(
        "\nSelect keyword number to remove (or press Enter to cancel)",
        choices=[*choices, ""],
        default="",
    )

    if not choice:
        console.print("[dim]Cancelled[/dim]")
        return

    keyword = mapping.blacklist_keywords.pop(int(choice) - 1)
    save_mapping(mapping, banks_dir)
    console.print(f"[green]✓[/green] Removed '{keyword}' from {mapping.bank_name} blacklist")


def manage_bank_blacklist(mapping: BankMapping, banks_dir: Path) -> None:
    """Interactive submenu for managing a single bank's blacklist."""
    while True:
        display_blacklist(mapping)

        console.print("\n[bold]Select action:[/bold]")
        console.print(" 1. Add keyword")
        console.print(" 2. Remove keyword")
        console.print(" 3. Back")

        choice = Prompt.ask("Enter choice", choices=["1", "2", "3"], default="3")

        match choice:
            case "1":
                add_keyword(mapping, banks_dir)
            case "2":
                remove_keyword(mapping, banks_dir)
            case _:
                break


def interactive_blacklist_management(banks_dir: Path) -> None:
    """Main entry point for interactive blacklist management."""
    console.print("\n[bold]Blacklist Management[/bold]")

    while True:
        banks = list_available_banks(banks_dir)

        if not banks:
            console.print("[yellow]No bank configurations found.[/yellow]")
            console.print(
                "Run 'budget-tracker process' with a CSV file to create a bank mapping first."
            )
            return

        console.print("\n[bold]Abailable banks:[/bold]")
        for i, b in enumerate(banks, start=1):
            console.print(f"    {i}. {b}")
        console.print(f"    {len(banks) + 1}. Exit")

        choices = [str(i) for i in range(1, len(banks) + 2)]
        choice = Prompt.ask("Select bank", choices=choices, default=str(len(banks) + 1))

        if int(choice) == len(banks) + 1:
            console.print("[dim]Exiting blacklist management[/dim]")
            break

        bank_name = banks[int(choice) - 1]
        mapping = load_mapping(bank_name, banks_dir)

        if not mapping:
            console.print(f"[red]Failed to load mapping for {bank_name}[/red]")
            continue

        manage_bank_blacklist(mapping, banks_dir)
