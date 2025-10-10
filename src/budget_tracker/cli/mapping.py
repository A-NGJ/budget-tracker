import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.config.settings import settings
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping

console = Console()


def interactive_column_mapping(
    file_path: Path, available_columns: list[str]
) -> BankMapping | None:
    """
    Guide user through interactive column mapping.

    Returns:
        BankMapping if successful, None if cancelled
    """
    console.print("\n[bold]Column Mapping Setup[/bold]")
    console.print(f"Available columns in CSV: {', '.join(available_columns)}\n")

    # Bank name
    bank_name = Prompt.ask(
        "Enter bank name (e.g., 'Danske Bank', 'Nordea')", default=file_path.stem
    )

    # Date column
    date_col = Prompt.ask(
        "Which column contains the transaction date?", choices=available_columns
    )

    # Amount column
    amount_col = Prompt.ask(
        "Which column contains the amount?", choices=available_columns
    )

    # Description column
    desc_col = Prompt.ask(
        "Which column contains the description/text?", choices=available_columns
    )

    # Date format - use default from settings
    date_format = settings.default_date_format
    console.print("\n[dim]Using date format: DD-MM-YYYY[/dim]")

    # Create mapping
    mapping = BankMapping(
        bank_name=bank_name,
        column_mapping=ColumnMapping(
            date_column=date_col, amount_column=amount_col, description_column=desc_col
        ),
        date_format=date_format,
    )

    # Confirm
    console.print("\n[bold green]Mapping created:[/bold green]")
    console.print(f"  Bank: {bank_name}")
    console.print(f"  Date: {date_col} (format: {date_format})")
    console.print(f"  Amount: {amount_col}")
    console.print(f"  Description: {desc_col}")

    save = Prompt.ask("\nSave this mapping?", choices=["y", "n"], default="y")

    if save == "y":
        return mapping
    return None


def save_mapping(mapping: BankMapping, mappings_file: Path) -> None:
    """Save bank mapping to JSON file"""
    mappings: dict[str, dict[str, object]] = {}
    if mappings_file.exists():
        with mappings_file.open() as f:
            mappings = json.load(f)

    mappings[mapping.bank_name] = mapping.model_dump()

    with mappings_file.open("w") as f:
        json.dump(mappings, f, indent=2)

    console.print(f"[green]✓[/green] Mapping saved for {mapping.bank_name}")


def load_mapping(bank_name: str, mappings_file: Path) -> BankMapping | None:
    """Load saved bank mapping by name"""
    if not mappings_file.exists():
        return None

    with mappings_file.open() as f:
        mappings = json.load(f)

    if bank_name in mappings:
        return BankMapping(**mappings[bank_name])
    return None
