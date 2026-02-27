from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.cli.selection import select_option

if TYPE_CHECKING:
    from budget_tracker.models.transaction import StandardTransaction


def parse_period_flags(
    from_date: str | None,
    to_date: str | None,
) -> AnalyticsPeriod:
    """Parse CLI date strings into an AnalyticsPeriod.

    Accepts ISO format (YYYY-MM-DD). Either flag can be None for open-ended ranges.
    Raises typer.BadParameter on invalid format.
    """
    parsed_from: date | None = None
    parsed_to: date | None = None

    if from_date is not None:
        try:
            parsed_from = date.fromisoformat(from_date)
        except ValueError as err:
            msg = f"Invalid date format '{from_date}'. Use YYYY-MM-DD."
            raise typer.BadParameter(msg) from err

    if to_date is not None:
        try:
            parsed_to = date.fromisoformat(to_date)
        except ValueError as err:
            msg = f"Invalid date format '{to_date}'. Use YYYY-MM-DD."
            raise typer.BadParameter(msg) from err

    label = _build_label(parsed_from, parsed_to)
    return AnalyticsPeriod(from_date=parsed_from, to_date=parsed_to, label=label)


def _build_label(from_date: date | None, to_date: date | None) -> str:
    """Build a human-readable label for a date range."""
    if from_date is None and to_date is None:
        return "All Time"
    from_str = from_date.strftime("%b %Y") if from_date else "..."
    to_str = to_date.strftime("%b %Y") if to_date else "..."
    return f"{from_str} - {to_str}"


def _count_in_range(
    transactions: list[StandardTransaction],
    from_date: date | None,
    to_date: date | None,
) -> int:
    """Count transactions within a date range."""
    count = 0
    for t in transactions:
        if from_date is not None and t.date < from_date:
            continue
        if to_date is not None and t.date > to_date:
            continue
        count += 1
    return count


def _build_presets(
    transactions: list[StandardTransaction],
) -> list[tuple[str, date | None, date | None]]:
    """Build preset options with labels and date ranges.

    Returns list of (label, from_date, to_date) tuples.
    """
    today = datetime.now(tz=UTC).date()
    presets: list[tuple[str, date | None, date | None]] = []

    # All time
    all_count = len(transactions)
    if transactions:
        min_date = min(t.date for t in transactions)
        max_date = max(t.date for t in transactions)
        date_range = f"{min_date.strftime('%b %Y')} - {max_date.strftime('%b %Y')}"
        presets.append((f"All time ({all_count} transactions, {date_range})", None, None))
    else:
        presets.append(("All time (0 transactions)", None, None))

    # Last month
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    last_month_count = _count_in_range(transactions, first_of_prev_month, last_of_prev_month)
    presets.append((
        f"Last month ({last_month_count} transactions)",
        first_of_prev_month,
        last_of_prev_month,
    ))

    # Last 3 months
    month_3_ago = today.month - 3
    year_3_ago = today.year
    if month_3_ago <= 0:
        month_3_ago += 12
        year_3_ago -= 1
    first_of_3_months_ago = date(year_3_ago, month_3_ago, 1)
    last_3_count = _count_in_range(transactions, first_of_3_months_ago, today)
    presets.append((
        f"Last 3 months ({last_3_count} transactions)",
        first_of_3_months_ago,
        today,
    ))

    # Last year
    prev_year = today.year - 1
    first_of_prev_year = date(prev_year, 1, 1)
    last_of_prev_year = date(prev_year, 12, 31)
    last_year_count = _count_in_range(transactions, first_of_prev_year, last_of_prev_year)
    presets.append((
        f"Last year ({last_year_count} transactions)",
        first_of_prev_year,
        last_of_prev_year,
    ))

    # Custom range
    presets.append(("Custom range...", None, None))

    return presets


def _prompt_custom_range() -> AnalyticsPeriod:
    """Prompt user for custom start and end dates."""
    console = Console()

    console.print("\n[bold]Enter custom date range (YYYY-MM-DD):[/bold]")

    from_str = Prompt.ask("  Start date (leave empty for open start)", default="")
    to_str = Prompt.ask("  End date (leave empty for open end)", default="")

    parsed_from: date | None = None
    parsed_to: date | None = None

    if from_str:
        try:
            parsed_from = date.fromisoformat(from_str)
        except ValueError:
            console.print(f"[red]Invalid date format '{from_str}'. Using open start.[/red]")

    if to_str:
        try:
            parsed_to = date.fromisoformat(to_str)
        except ValueError:
            console.print(f"[red]Invalid date format '{to_str}'. Using open end.[/red]")

    label = _build_label(parsed_from, parsed_to)
    return AnalyticsPeriod(from_date=parsed_from, to_date=parsed_to, label=label)


def select_period_interactive(
    transactions: list[StandardTransaction],
) -> AnalyticsPeriod:
    """Show interactive period selection prompt with presets.

    Returns the selected AnalyticsPeriod.
    """
    presets = _build_presets(transactions)
    labels = [p[0] for p in presets]

    selected = select_option("Select analytics period:", labels)

    # Find the matching preset
    for label, from_date, to_date in presets:
        if label == selected:
            if "Custom range" in label:
                return _prompt_custom_range()
            period_label = _build_label(from_date, to_date)
            return AnalyticsPeriod(from_date=from_date, to_date=to_date, label=period_label)

    # Fallback (shouldn't reach here)
    return AnalyticsPeriod(from_date=None, to_date=None, label="All Time")


def resolve_period(
    from_date_flag: str | None,
    to_date_flag: str | None,
    transactions: list[StandardTransaction],
    no_interactive: bool = False,
) -> AnalyticsPeriod:
    """Resolve the analytics period from flags or interactive selection.

    Priority:
    1. If CLI flags provided → parse them (no prompt)
    2. If non-interactive mode → default to all-time
    3. Otherwise → interactive prompt with presets
    """
    if from_date_flag is not None or to_date_flag is not None:
        return parse_period_flags(from_date_flag, to_date_flag)

    if no_interactive:
        return AnalyticsPeriod(from_date=None, to_date=None, label="All Time")

    return select_period_interactive(transactions)
