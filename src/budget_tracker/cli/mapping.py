import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.config.settings import settings
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping

console = Console()


def interactive_column_mapping(file_path: Path, available_columns: list[str]) -> BankMapping | None:
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
    date_col = Prompt.ask("Which column contains the transaction date?", choices=available_columns)

    # Amount column
    amount_col = Prompt.ask("Which column contains the amount?", choices=available_columns)

    # Description column
    desc_col = Prompt.ask("Which column contains the description/text?", choices=available_columns)

    # Currency handling
    console.print("\n[bold]Currency Configuration[/bold]")
    has_currency_column = Prompt.ask(
        "Does the CSV have a currency column?", choices=["y", "n"], default="n"
    )

    currency_col = None
    default_currency = "DKK"

    if has_currency_column == "y":
        currency_col = Prompt.ask(
            "Which column contains the currency code?", choices=available_columns
        )
    else:
        # Ask for default currency
        console.print("\nCommon currencies:")
        console.print("  1. DKK (Danish Krone)")
        console.print("  2. EUR (Euro)")
        console.print("  3. USD (US Dollar)")
        console.print("  4. GBP (British Pound)")
        console.print("  5. SEK (Swedish Krona)")
        console.print("  6. NOK (Norwegian Krone)")
        console.print("  7. Other")

        currency_choice = Prompt.ask("Select currency", default="1")

        currency_map = {
            "1": "DKK",
            "2": "EUR",
            "3": "USD",
            "4": "GBP",
            "5": "SEK",
            "6": "NOK",
        }

        if currency_choice == "7":
            default_currency = Prompt.ask("Enter currency code (e.g., CHF, JPY)")
        else:
            default_currency = currency_map.get(currency_choice, "DKK")

    # Date format
    console.print("\n[bold]Date Format Configuration[/bold]")
    console.print("What date format does your CSV use?")
    console.print("  1. DD-MM-YYYY (e.g., 31-12-2024)")
    console.print("  2. YYYY-MM-DD (e.g., 2024-12-31)")
    console.print("  3. MM/DD/YYYY (e.g., 12/31/2024)")
    console.print("  4. DD/MM/YYYY (e.g., 31/12/2024)")
    console.print("  5. YYYY/MM/DD (e.g., 2024/12/31)")
    console.print("  6. Other")

    date_format_choice = Prompt.ask("Select date format", choices=["1", "2", "3", "4", "5", "6"], default="1")

    date_format_map = {
        "1": "%d-%m-%Y",
        "2": "%Y-%m-%d",
        "3": "%m/%d/%Y",
        "4": "%d/%m/%Y",
        "5": "%Y/%m/%d",
    }

    if date_format_choice == "6":
        console.print("\nEnter custom date format using Python strftime codes:")
        console.print("  %d = day, %m = month, %Y = year")
        console.print("  Example: '%d.%m.%Y' for 31.12.2024")
        date_format = Prompt.ask("Enter date format")
    else:
        date_format = date_format_map.get(date_format_choice, settings.default_date_format)

    # Decimal separator
    console.print("\n[bold]Decimal Separator Configuration[/bold]")
    console.print("What character is used for decimal separation?")
    console.print("  1. . (dot/period) - e.g., 1234.56")
    console.print("  2. , (comma) - e.g., 1234,56")

    decimal_choice = Prompt.ask("Select decimal separator", choices=["1", "2"], default="1")
    decimal_separator = "." if decimal_choice == "1" else ","

    # Create mapping
    mapping = BankMapping(
        bank_name=bank_name,
        column_mapping=ColumnMapping(
            date_column=date_col,
            amount_column=amount_col,
            description_column=desc_col,
            currency_column=currency_col,
        ),
        date_format=date_format,
        default_currency=default_currency,
        decimal_separator=decimal_separator,
    )

    # Confirm
    console.print("\n[bold green]Mapping created:[/bold green]")
    console.print(f"  Bank: {bank_name}")
    console.print(f"  Date: {date_col} (format: {date_format})")
    console.print(f"  Amount: {amount_col}")
    console.print(f"  Description: {desc_col}")
    console.print(f"  Currency: {currency_col or default_currency}")
    console.print(f"  Decimal separator: {decimal_separator}")

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

    for name in mappings:
        if name.lower() in bank_name.lower():
            return BankMapping(**mappings[name])
    return None
