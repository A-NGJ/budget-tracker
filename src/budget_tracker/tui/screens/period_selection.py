"""Period selection screen for filtering transactions by date range."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.parsers.csv_parser import ParsedTransaction
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Period Selection[/b]

  [cyan]↑/↓[/cyan]     Navigate presets
  [cyan]Enter[/cyan]   Select period
  [cyan]Escape[/cyan]  Go back

[b]Custom Range[/b]

  When "Custom range..." is highlighted,
  enter start/end dates in YYYY-MM-DD format.
  Leave empty for open-ended ranges.
"""

CUSTOM_RANGE_INDEX = 4  # Index of "Custom range..." in presets


def _build_label(from_date: date | None, to_date: date | None) -> str:
    """Build a human-readable label for a date range."""
    if from_date is None and to_date is None:
        return "All Time"
    from_str = from_date.strftime("%b %Y") if from_date else "..."
    to_str = to_date.strftime("%b %Y") if to_date else "..."
    return f"{from_str} - {to_str}"


def _count_in_range(
    transactions: list[ParsedTransaction],
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
    transactions: list[ParsedTransaction],
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
    presets.append(
        (
            f"Last month ({last_month_count} transactions)",
            first_of_prev_month,
            last_of_prev_month,
        )
    )

    # Last 3 months
    month_3_ago = today.month - 3
    year_3_ago = today.year
    if month_3_ago <= 0:
        month_3_ago += 12
        year_3_ago -= 1
    first_of_3_months_ago = date(year_3_ago, month_3_ago, 1)
    last_3_count = _count_in_range(transactions, first_of_3_months_ago, today)
    presets.append(
        (
            f"Last 3 months ({last_3_count} transactions)",
            first_of_3_months_ago,
            today,
        )
    )

    # Last year
    prev_year = today.year - 1
    first_of_prev_year = date(prev_year, 1, 1)
    last_of_prev_year = date(prev_year, 12, 31)
    last_year_count = _count_in_range(transactions, first_of_prev_year, last_of_prev_year)
    presets.append(
        (
            f"Last year ({last_year_count} transactions)",
            first_of_prev_year,
            last_of_prev_year,
        )
    )

    # Custom range
    presets.append(("Custom range...", None, None))

    return presets


class PeriodSelectionScreen(Screen):
    """Select the analytics time range before categorization."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._presets: list[tuple[str, date | None, date | None]] = []

    def compose(self) -> ComposeResult:
        yield Static("Select Period", id="title")
        yield OptionList(id="preset-list")
        with Vertical(id="custom-range-inputs"):
            yield Static("Enter date range (YYYY-MM-DD):", id="custom-label")
            yield Input(placeholder="Start date (leave empty for open start)", id="from-date")
            yield Input(placeholder="End date (leave empty for open end)", id="to-date")
        yield Footer()

    def on_mount(self) -> None:
        transactions = self.app.pipeline_state.transactions_to_categorize
        self._presets = _build_presets(transactions)

        option_list = self.query_one("#preset-list", OptionList)
        for label, _, _ in self._presets:
            option_list.add_option(Option(label))

        option_list.highlighted = 0
        self.query_one("#custom-range-inputs").display = False
        option_list.focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        is_custom = event.option_index == CUSTOM_RANGE_INDEX
        self.query_one("#custom-range-inputs").display = is_custom

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if index == CUSTOM_RANGE_INDEX:
            self._handle_custom_range()
        else:
            _label, from_date, to_date = self._presets[index]
            period_label = _build_label(from_date, to_date)
            period = AnalyticsPeriod(from_date=from_date, to_date=to_date, label=period_label)
            self._finish(period)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("from-date", "to-date"):
            self._handle_custom_range()

    def _handle_custom_range(self) -> None:
        from_str = self.query_one("#from-date", Input).value.strip()
        to_str = self.query_one("#to-date", Input).value.strip()

        parsed_from: date | None = None
        parsed_to: date | None = None

        if from_str:
            try:
                parsed_from = date.fromisoformat(from_str)
            except ValueError:
                self.notify(f"Invalid date: '{from_str}'. Use YYYY-MM-DD.", severity="error")
                return

        if to_str:
            try:
                parsed_to = date.fromisoformat(to_str)
            except ValueError:
                self.notify(f"Invalid date: '{to_str}'. Use YYYY-MM-DD.", severity="error")
                return

        label = _build_label(parsed_from, parsed_to)
        period = AnalyticsPeriod(from_date=parsed_from, to_date=parsed_to, label=label)
        self._finish(period)

    def _finish(self, period: AnalyticsPeriod) -> None:
        state = self.app.pipeline_state
        state.period = period

        # Filter transactions to selected period
        filtered = []
        for txn in state.transactions_to_categorize:
            if period.from_date and txn.date < period.from_date:
                continue
            if period.to_date and txn.date > period.to_date:
                continue
            filtered.append(txn)
        state.transactions_to_categorize = filtered

        self.app.push_screen("categorization")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
