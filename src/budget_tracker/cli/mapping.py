from pathlib import Path

import yaml
from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.config.settings import get_settings
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping

console = Console()


def interactive_column_mapping(  # noqa: PLR0912,PLR0915
    file_path: Path,
    columns: list[str],
    bank_name: str | None = None,
) -> BankMapping | None:
    """
    Guide user through interactive column mapping.

    Returns:
        BankMapping if successful, None if cancelled
    """
    console.print("\n[bold]Column Mapping Setup[/bold]")
    console.print(f"Available columns in CSV: {', '.join(columns)}\n")

    # Bank name
    bank_name = Prompt.ask(
        "Enter bank name (e.g., 'Danske Bank', 'Nordea')", default=file_path.stem
    )

    # Date column
    date_col = Prompt.ask("Which column contains the transaction date?", choices=columns)

    # Amount column
    amount_col = Prompt.ask("Which column contains the amount?", choices=columns)

    # Description columns (can be multiple)
    console.print("\n[bold]Description Column(s)[/bold]")
    console.print("You can select one or more columns to combine into the description.")
    console.print(
        "Multiple columns will be joined with || separator "
        "(e.g., 'Text || Category || Subcategory')"
    )

    desc_cols: list[str] = []
    while True:
        # Filter out already selected columns from choices
        remaining_cols = [
            col for col in columns if col not in desc_cols and col not in [date_col, amount_col]
        ]

        if not remaining_cols:
            console.print("[yellow]No more columns available to select.[/yellow]")
            break

        if desc_cols:
            console.print(f"\n[dim]Currently selected: {' + '.join(desc_cols)}[/dim]")
            add_more = Prompt.ask("Add another column?", choices=["y", "n"], default="n")
            if add_more == "n":
                break

        desc_col = Prompt.ask(
            "Which column contains description/text?" if not desc_cols else "Select another column",
            choices=remaining_cols,
        )
        desc_cols.append(desc_col)

    if not desc_cols:
        console.print("[red]Error: At least one description column is required[/red]")
        return None

    # Currency handling
    console.print("\n[bold]Currency Configuration[/bold]")
    has_currency_column = Prompt.ask(
        "Does the CSV have a currency column?", choices=["y", "n"], default="n"
    )

    currency_col = None
    default_currency = "DKK"

    if has_currency_column == "y":
        currency_col = Prompt.ask("Which column contains the currency code?", choices=columns)
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

    date_format_choice = Prompt.ask(
        "Select date format", choices=["1", "2", "3", "4", "5", "6"], default="1"
    )

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
        date_format = date_format_map.get(date_format_choice, get_settings().default_date_format)

    # Decimal separator
    console.print("\n[bold]Decimal Separator Configuration[/bold]")
    console.print("What character is used for decimal separation?")
    console.print("  1. . (dot/period) - e.g., 1234.56")
    console.print("  2. , (comma) - e.g., 1234,56")

    decimal_choice = Prompt.ask("Select decimal separator", choices=["1", "2"], default="1")
    decimal_separator = "." if decimal_choice == "1" else ","

    if not bank_name:
        bank_name = Prompt.ask("Enter bank name for this mapping", default=file_path.stem)

    # Create mapping
    mapping = BankMapping(
        bank_name=bank_name,
        column_mapping=ColumnMapping(
            date_column=date_col,
            amount_column=amount_col,
            description_columns=desc_cols,
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
    console.print(f"  Description: {' || '.join(desc_cols)}")
    console.print(f"  Currency: {currency_col or default_currency}")
    console.print(f"  Decimal separator: {decimal_separator}")

    save = Prompt.ask("\nSave this mapping?", choices=["y", "n"], default="y")

    if save == "y":
        return mapping
    return None


def save_mapping(mapping: BankMapping, banks_dir: Path) -> None:
    """Save bank mapping to YAML file

    Args:
        mapping: BankMapping to save
        banks_dir: Directory to save YAML file in
    """
    banks_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = banks_dir / f"{mapping.bank_name}.yaml"

    with mapping_file.open("w") as f:
        yaml.safe_dump(mapping.model_dump(), f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]✓[/green] Mapping saved to {mapping_file}")


def load_mapping(bank_name: str, banks_dir: Path) -> BankMapping | None:
    """Load bank mapping from YAML file

    Args:
        bank_name: Exact bank name (matches filename without .yaml)
        banks_dir: Direectory containing bank YAML files

    Returns:
        BankMapping if found, None otherwise
    """

    mapping_file = banks_dir / f"{bank_name}.yaml"

    if not mapping_file.exists():
        return None

    with mapping_file.open() as f:
        data = yaml.safe_load(f)

    return BankMapping.model_validate(data)
