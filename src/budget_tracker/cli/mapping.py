from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import yaml
from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.cli.selection import select_option
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping

console = Console()


class MappingStep(Enum):
    BANK_NAME = auto()
    DATE_COLUMN = auto()
    AMOUNT_COLUMN = auto()
    DESCRIPTION_COLUMNS = auto()
    CURRENCY_CONFIG = auto()
    DATE_FORMAT = auto()
    DECIMAL_SEPARATOR = auto()
    CONFIRM = auto()


class StepResult(Enum):
    NEXT = auto()
    BACK = auto()
    CANCEL = auto()
    DONE = auto()


@dataclass
class MappingState:
    """Tracks collected values during mapping flow."""

    bank_name: str | None = None
    date_col: str | None = None
    amount_col: str | None = None
    desc_cols: list[str] = field(default_factory=list)
    currency_col: str | None = None
    default_currency: str = "DKK"
    has_currency_column: bool = False
    date_format: str | None = None
    decimal_separator: str | None = None


def interactive_column_mapping(
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
    console.print("[dim]Tip: Select '← Go Back' to return to previous step[/dim]\n")

    state = MappingState(bank_name=bank_name)
    steps = list(MappingStep)
    step_index = 0

    while step_index < len(steps):
        current_step = steps[step_index]
        allow_back = step_index > 0  # Can't go back from the first step

        result = _execute_step(current_step, state, columns, allow_back)

        match result:
            case StepResult.BACK:
                step_index = max(0, step_index - 1)
            case StepResult.CANCEL:
                return None
            case StepResult.DONE:
                # Build and return the mapping
                return _build_mapping(state)
            case StepResult.NEXT:
                step_index += 1

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


def _execute_step(  # noqa: PLR0911
    step: MappingStep,
    state: MappingState,
    columns: list[str],
    allow_back: bool,
) -> StepResult:
    """Execute a single step"""
    match step:
        case MappingStep.BANK_NAME:
            return _step_bank_name(state)
        case MappingStep.DATE_COLUMN:
            return _step_date_column(state, columns, allow_back)
        case MappingStep.AMOUNT_COLUMN:
            return _step_amount_column(state, columns, allow_back)
        case MappingStep.DESCRIPTION_COLUMNS:
            return _step_description_columns(state, columns, allow_back)
        case MappingStep.CURRENCY_CONFIG:
            return _step_currency_config(state, columns, allow_back)
        case MappingStep.DATE_FORMAT:
            return _step_date_format(state, allow_back)
        case MappingStep.DECIMAL_SEPARATOR:
            return _step_decimal_separator(state, allow_back)
        case MappingStep.CONFIRM:
            return _step_confirm(state, allow_back)
    return StepResult.NEXT


def _step_bank_name(state: MappingState) -> StepResult:
    """Step 1: Bank name (no back from first step)."""
    state.bank_name = Prompt.ask(
        "Enter bank name (e.g., 'Danske Bank', 'Nordea')",
        default=state.bank_name,
    )
    return StepResult.NEXT


def _step_date_column(state: MappingState, columns: list[str], allow_back: bool) -> StepResult:
    """Step 2: Date column selection."""
    result = select_option(
        "Which column contains the transaction date?",
        columns,
        default=state.date_col,
        allow_back=allow_back,
    )
    if result is None:
        return StepResult.BACK
    state.date_col = result
    return StepResult.NEXT


def _step_amount_column(state: MappingState, columns: list[str], allow_back: bool) -> StepResult:
    """Step 3: Amount column selection."""
    result = select_option(
        "Which column contains the transaction amount?",
        columns,
        default=state.amount_col,
        allow_back=allow_back,
    )
    if result is None:
        return StepResult.BACK
    state.amount_col = result
    return StepResult.NEXT


def _step_description_columns(
    state: MappingState, columns: list[str], allow_back: bool
) -> StepResult:
    """Step 4: Description column(s) selection."""
    console.print("\n[bold]Description Column(s)[/bold]")
    console.print("You can select one or more columns to combine into the description.")
    console.print(
        "Multiple columns will be joined with || separator "
        "(e.g., 'Text || Category || Subcategory')"
    )

    # Start fresh or continue from saved state
    desc_cols: list[str] = list(state.desc_cols) if state.desc_cols else []

    while True:
        remaining_cols = [
            col
            for col in columns
            if col not in desc_cols and col not in [state.date_col, state.amount_col]
        ]

        if not remaining_cols:
            console.print("[yellow]No more columns available to select.[/yellow]")
            break

        if desc_cols:
            console.print(f"\n[dim]Currently selected: {' + '.join(desc_cols)}[/dim]")
            add_more = Prompt.ask("Add another column?", choices=["y", "n"], default="n")
            if add_more == "n":
                break

        desc_col = select_option(
            "Which column contains description/text?" if not desc_cols else "Select another column",
            remaining_cols,
            allow_back=allow_back,
        )
        if desc_col is None:
            return StepResult.BACK
        desc_cols.append(desc_col)

    if not desc_cols:
        console.print("[red]Error: At least one description column is required[/red]")
        return StepResult.BACK  # Go back to try again

    state.desc_cols = desc_cols
    return StepResult.NEXT


def _step_currency_config(state: MappingState, columns: list[str], allow_back: bool) -> StepResult:
    """Step 5: Currency configuration."""
    console.print("\n[bold]Currency Configuration[/bold]")

    has_currency_choices = ["Yes - CSV has a currency column", "No - use default currency"]
    default_currency_choice = (
        has_currency_choices[0] if state.has_currency_column else has_currency_choices[1]
    )

    has_currency_selection = select_option(
        "Does the CSV have a currency column?",
        has_currency_choices,
        default=default_currency_choice,
        allow_back=allow_back,
    )

    if has_currency_selection is None:
        return StepResult.BACK

    state.has_currency_column = has_currency_selection.startswith("Yes")

    if state.has_currency_column:
        result = select_option(
            "Which column contains the currency code?",
            columns,
            default=state.currency_col,
            allow_back=allow_back,
        )
        if result is None:
            return StepResult.BACK
        state.currency_col = result
    else:
        state.currency_col = None
        currency_choices = [
            "DKK (Danish Krone)",
            "EUR (Euro)",
            "USD (US Dollar)",
            "GBP (British Pound)",
            "SEK (Swedish Krona)",
            "NOK (Norwegian Krone)",
            "Other",
        ]

        # Find default based on saved state
        default_choice = None
        for choice in currency_choices:
            if choice.startswith(state.default_currency):
                default_choice = choice
                break

        currency_selection = select_option(
            "Select currency",
            currency_choices,
            default=default_choice or "DKK (Danish Krone)",
            allow_back=allow_back,
        )

        if currency_selection is None:
            return StepResult.BACK

        if currency_selection == "Other":
            state.default_currency = Prompt.ask(
                "Enter currency code (e.g., CHF, JPY)",
                default=state.default_currency,
            )
        else:
            state.default_currency = currency_selection.split()[0]

    return StepResult.NEXT


def _step_date_format(state: MappingState, allow_back: bool) -> StepResult:
    """Step 6: Date format selection."""
    console.print("\n[bold]Date Format Configuration[/bold]")

    date_format_choices = [
        "DD-MM-YYYY (e.g., 31-12-2024)",
        "YYYY-MM-DD (e.g., 2024-12-31)",
        "MM/DD/YYYY (e.g., 12/31/2024)",
        "DD/MM/YYYY (e.g., 31/12/2024)",
        "YYYY/MM/DD (e.g., 2024/12/31)",
        "DD.MM.YYYY (e.g., 31.12.2024)",
        "Other",
    ]
    date_format_map = {
        "DD-MM-YYYY (e.g., 31-12-2024)": "%d-%m-%Y",
        "YYYY-MM-DD (e.g., 2024-12-31)": "%Y-%m-%d",
        "MM/DD/YYYY (e.g., 12/31/2024)": "%m/%d/%Y",
        "DD/MM/YYYY (e.g., 31/12/2024)": "%d/%m/%Y",
        "YYYY/MM/DD (e.g., 2024/12/31)": "%Y/%m/%d",
        "DD.MM.YYYY (e.g., 31.12.2024)": "%d.%m.%Y",
    }

    # Find default choice based on saved state
    default_choice = None
    if state.date_format:
        for label, fmt in date_format_map.items():
            if fmt == state.date_format:
                default_choice = label
                break

    date_format_selection = select_option(
        "What date format does your file use?",
        date_format_choices,
        default=default_choice,
        allow_back=allow_back,
    )

    if date_format_selection is None:
        return StepResult.BACK

    if date_format_selection == "Other":
        console.print("\nEnter custom date format using Python strftime codes:")
        console.print("  %d = day, %m = month, %Y = year")
        console.print("  Example: '%d.%m.%Y' for 31.12.2024")
        state.date_format = Prompt.ask(
            "Enter date format",
            default=state.date_format or "%Y-%m-%d",
        )
    else:
        state.date_format = date_format_map[date_format_selection]

    return StepResult.NEXT


def _step_decimal_separator(state: MappingState, allow_back: bool) -> StepResult:
    """Step 7: Decimal separator selection."""
    console.print("\n[bold]Decimal Separator Configuration[/bold]")

    decimal_choices = [
        ". (dot/period) - e.g., 1234.56",
        ", (comma) - e.g., 1234,56",
    ]

    # Find default based on saved state
    default_choice = None
    if state.decimal_separator == ".":
        default_choice = decimal_choices[0]
    elif state.decimal_separator == ",":
        default_choice = decimal_choices[1]

    decimal_selection = select_option(
        "What character is used for decimal separation?",
        decimal_choices,
        default=default_choice or decimal_choices[0],
        allow_back=allow_back,
    )

    if decimal_selection is None:
        return StepResult.BACK

    state.decimal_separator = "." if decimal_selection.startswith(".") else ","
    return StepResult.NEXT


def _step_confirm(state: MappingState, allow_back: bool) -> StepResult:
    """Final confirmation step."""
    console.print("\n[bold green]Mapping created:[/bold green]")
    console.print(f"  Bank: {state.bank_name}")
    console.print(f"  Date: {state.date_col} (format: {state.date_format})")
    console.print(f"  Amount: {state.amount_col}")
    console.print(f"  Description: {' || '.join(state.desc_cols)}")
    console.print(f"  Currency: {state.currency_col or state.default_currency}")
    console.print(f"  Decimal separator: {state.decimal_separator}")

    save_choices = ["Yes - save this mapping", "No - cancel"]
    save_selection = select_option(
        "Save this mapping?",
        save_choices,
        default="Yes - save this mapping",
        allow_back=allow_back,
    )

    if save_selection is None:
        return StepResult.BACK
    if save_selection.startswith("Yes"):
        return StepResult.DONE
    return StepResult.CANCEL


def _build_mapping(state: MappingState) -> BankMapping:
    """Build BankMapping from collected state."""
    if state.bank_name is None:
        msg = "bank_name is required"
        raise ValueError(msg)
    if state.date_col is None:
        msg = "date_col is required"
        raise ValueError(msg)
    if state.amount_col is None:
        msg = "amount_col is required"
        raise ValueError(msg)
    if not state.desc_cols:
        msg = "desc_cols is required"
        raise ValueError(msg)
    if state.date_format is None:
        msg = "date_format is required"
        raise ValueError(msg)
    if state.decimal_separator is None:
        msg = "decimal_separator is required"
        raise ValueError(msg)

    return BankMapping(
        bank_name=state.bank_name,
        column_mapping=ColumnMapping(
            date_column=state.date_col,
            amount_column=state.amount_col,
            description_columns=state.desc_cols,
            currency_column=state.currency_col,
        ),
        date_format=state.date_format,
        default_currency=state.default_currency,
        decimal_separator=state.decimal_separator,
    )
