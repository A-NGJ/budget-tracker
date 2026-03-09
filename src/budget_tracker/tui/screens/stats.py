"""Statistics screen with filtering and export."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Input,
    OptionList,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.analytics.models import AnalyticsResult
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Statistics[/b]

  [cyan]1/2/3[/cyan]         Switch tabs
  [cyan]Tab/Shift+Tab[/cyan]  Cycle focus
  [cyan]↑/↓[/cyan]           Navigate options
  [cyan]E[/cyan]             Jump to export
  [cyan]Escape[/cyan]        Go back
  [cyan]?[/cyan]             Show this help

[b]Filters[/b]

  Source, Category, Subcategory, Period
  Keyword — free-text search

[b]Export[/b]

  Excel — .xlsx with analytics sheet
  CSV   — plain transactions
"""

MAX_BAR_WIDTH = 20

EXPORT_FORMATS = [
    ("Excel (.xlsx)", "excel"),
    ("CSV (.csv)", "csv"),
]

ALL_SENTINEL = ""

PERIOD_PRESETS = [
    "All time",
    "Last month",
    "Last 3 months",
    "Last 6 months",
    "Last year",
]


def _period_to_dates(preset: str) -> tuple[date | None, date | None]:
    """Convert a period preset label to (from_date, to_date)."""
    today = datetime.now(tz=UTC).date()
    if preset == "All time":
        return (None, None)
    if preset == "Last month":
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        return (first_of_prev_month, last_of_prev_month)
    if preset == "Last 3 months":
        month = today.month - 3
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        return (date(year, month, 1), today)
    if preset == "Last 6 months":
        month = today.month - 6
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        return (date(year, month, 1), today)
    if preset == "Last year":
        prev_year = today.year - 1
        return (date(prev_year, 1, 1), date(prev_year, 12, 31))
    return (None, None)


class StatsScreen(Screen):
    """Display statistics with filtering and export."""

    app: BudgetTrackerApp

    CSS_PATH = "../styles/stats.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "vim_down", "Down", show=False),
        Binding("k", "vim_up", "Up", show=False),
        Binding("escape", "go_back", "Back"),
        Binding("e", "focus_export", "Export", key_display="E"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("1", "switch_tab('tab-overview')", "Overview", show=False),
        Binding("2", "switch_tab('tab-monthly')", "Monthly", show=False),
        Binding("3", "switch_tab('tab-sources')", "Sources", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Statistics", id="title")

        # Empty state
        yield Static(
            "No transactions saved yet.\n"
            "Process bank statements first to build your history.\n\n"
            "  [bold cyan]\\[Escape][/] Back",
            id="empty-state",
        )

        # Filter bar
        with Vertical(id="filter-bar"):
            with Horizontal(id="filter-row-1"):
                yield Select[str]([], id="source-select", prompt="Source")
                yield Select[str]([], id="category-select", prompt="Category")
                yield Select[str]([], id="subcategory-select", prompt="Subcategory")
            with Horizontal(id="filter-row-2"):
                yield Select[str]([], id="period-select", prompt="Period")
                yield Input(placeholder="Keyword search...", id="keyword-input")

        # Tabbed analytics content
        with TabbedContent(id="stats-tabs"):
            with TabPane("Overview", id="tab-overview"):
                yield Static("", id="summary")
                yield DataTable(id="category-table")
            with TabPane("Monthly", id="tab-monthly"):
                yield DataTable(id="monthly-table")
            with TabPane("Sources", id="tab-sources"):
                yield DataTable(id="source-table")

        # Export section
        with Vertical(id="export-section"):
            yield Static("Select export format:", id="format-label")
            yield OptionList(id="format-list")
        yield Static("", id="export-result")

        yield Footer()

    def on_mount(self) -> None:
        # Hide everything initially
        self.query_one("#empty-state").display = False
        self.query_one("#filter-bar").display = False
        self.query_one("#stats-tabs").display = False
        self.query_one("#export-section").display = False
        self.query_one("#export-result").display = False

        if self.app.service.transaction_count() == 0:
            self.query_one("#empty-state").display = True
            return

        self._populate_filters()
        self.query_one("#filter-bar").display = True
        self.query_one("#stats-tabs").display = True
        self.query_one("#export-section").display = True

        # Setup export format list
        format_list = self.query_one("#format-list", OptionList)
        for label, _ in EXPORT_FORMATS:
            format_list.add_option(Option(label))
        format_list.highlighted = 0

        self._recompute()

    def _populate_filters(self) -> None:
        sources = self.app.service.get_transaction_sources()
        categories = self.app.service.get_transaction_categories()

        source_select = self.query_one("#source-select", Select)
        source_options: list[tuple[str, str]] = [("All sources", ALL_SENTINEL)]
        source_options.extend((s, s) for s in sources)
        source_select.set_options(source_options)
        source_select.value = ALL_SENTINEL

        cat_select = self.query_one("#category-select", Select)
        cat_options: list[tuple[str, str]] = [("All categories", ALL_SENTINEL)]
        cat_options.extend((c, c) for c in categories)
        cat_select.set_options(cat_options)
        cat_select.value = ALL_SENTINEL

        sub_select = self.query_one("#subcategory-select", Select)
        sub_select.set_options([("All subcategories", ALL_SENTINEL)])
        sub_select.value = ALL_SENTINEL
        sub_select.disabled = True

        period_select = self.query_one("#period-select", Select)
        period_options: list[tuple[str, str]] = [(p, p) for p in PERIOD_PRESETS]
        period_select.set_options(period_options)
        period_select.value = PERIOD_PRESETS[0]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "category-select":
            self._update_subcategory_options()
        self._recompute()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "keyword-input":
            self._recompute()

    def _update_subcategory_options(self) -> None:
        cat_value = self.query_one("#category-select", Select).value
        sub_select = self.query_one("#subcategory-select", Select)

        if cat_value == ALL_SENTINEL or cat_value is Select.BLANK:
            sub_select.set_options([("All subcategories", ALL_SENTINEL)])
            sub_select.value = ALL_SENTINEL
            sub_select.disabled = True
        else:
            subcats = self.app.service.get_transaction_subcategories(str(cat_value))
            sub_options: list[tuple[str, str]] = [("All subcategories", ALL_SENTINEL)]
            sub_options.extend((s, s) for s in subcats)
            sub_select.set_options(sub_options)
            sub_select.value = ALL_SENTINEL
            sub_select.disabled = False

    def _recompute(self) -> None:
        source_val = self.query_one("#source-select", Select).value
        cat_val = self.query_one("#category-select", Select).value
        sub_val = self.query_one("#subcategory-select", Select).value
        period_val = self.query_one("#period-select", Select).value
        keyword_val = self.query_one("#keyword-input", Input).value.strip()

        source = str(source_val) if source_val and source_val != ALL_SENTINEL else None
        category = str(cat_val) if cat_val and cat_val != ALL_SENTINEL else None
        subcategory = str(sub_val) if sub_val and sub_val != ALL_SENTINEL else None
        keyword = keyword_val if keyword_val else None

        period_label = str(period_val) if period_val else "All time"
        from_date, to_date = _period_to_dates(period_label)

        filtered = self.app.service.get_filtered_transactions(
            source=source,
            category=category,
            subcategory=subcategory,
            from_date=from_date,
            to_date=to_date,
            keyword=keyword,
        )

        period = AnalyticsPeriod(from_date=from_date, to_date=to_date, label=period_label)
        result = self.app.service.compute_analytics(filtered, period)
        self._filtered_transactions = filtered
        self._analytics_result = result
        self._update_overview(result, len(filtered))
        self._update_monthly(result)
        self._update_sources(result)

    def _update_overview(self, result: AnalyticsResult, count: int) -> None:
        # Update title
        title = self.query_one("#title", Static)
        title.update(f"Statistics — {result.period.label} ({count:,} transactions)")

        # Render summary
        summary = result.summary
        net_style = "green" if summary.net >= 0 else "red"
        summary_text = (
            f"  Transactions:  {summary.total_transactions}\n"
            f"  Income:        [green]{summary.total_income:,.2f} DKK[/green]\n"
            f"  Expenses:      [red]{summary.total_expenses:,.2f} DKK[/red]\n"
            f"  Net:           [{net_style}]{summary.net:,.2f} DKK[/{net_style}]"
        )
        self.query_one("#summary", Static).update(summary_text)

        # Render category table
        table = self.query_one("#category-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Category", "Amount (DKK)", "%", "")
        max_pct = result.category_data[0].percentage if result.category_data else 1.0
        for row in result.category_data:
            bar_len = int(row.percentage / max_pct * MAX_BAR_WIDTH) if max_pct > 0 else 0
            bar = "\u2588" * bar_len
            table.add_row(
                row.category,
                f"{row.total:,.2f}",
                f"{row.percentage:.1f}%",
                bar,
            )

    def _update_monthly(self, result: AnalyticsResult) -> None:
        """Update monthly tab with income/expenses/net per month."""
        table = self.query_one("#monthly-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Month", "Income", "Expenses", "Net", "Count", "")

        rows = list(reversed(result.monthly_data))
        max_expenses = max((abs(r.expenses) for r in rows), default=0)

        for row in rows:
            income_text = f"[green]+{row.income:,.0f} DKK[/green]"
            expenses_text = f"[red]{row.expenses:,.0f} DKK[/red]"
            net_style = "green" if row.net >= 0 else "red"
            net_text = f"[{net_style}]{row.net:,.0f} DKK[/{net_style}]"

            bar_len = (
                int(abs(row.expenses) / max_expenses * MAX_BAR_WIDTH) if max_expenses > 0 else 0
            )
            bar = "\u2588" * bar_len

            table.add_row(
                row.label,
                income_text,
                expenses_text,
                net_text,
                str(row.transaction_count),
                bar,
            )

    def _update_sources(self, result: AnalyticsResult) -> None:
        """Update sources tab — stub for stab-003."""

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if 0 <= index < len(EXPORT_FORMATS):
            _label, format_key = EXPORT_FORMATS[index]
            self._run_export(format_key)

    @work(thread=True)
    def _run_export(self, format_key: str) -> None:
        try:
            if format_key == "excel":
                path = self.app.service.export_excel(
                    self._filtered_transactions, self._analytics_result
                )
            elif format_key == "csv":
                path = self.app.service.export_csv(self._filtered_transactions)
            else:
                return

            self.app.call_from_thread(self._on_export_success, path)
        except Exception as exc:
            self.app.call_from_thread(self._on_export_error, str(exc))

    def _on_export_success(self, path: str) -> None:
        result_widget = self.query_one("#export-result", Static)
        result_widget.update(f"[bold green]Exported successfully:[/bold green] {path}")
        result_widget.display = True

    def _on_export_error(self, error: str) -> None:
        result_widget = self.query_one("#export-result", Static)
        result_widget.update(f"[bold red]Export failed:[/bold red] {error}")
        result_widget.display = True

    def action_vim_down(self) -> None:
        focused = self.app.focused
        if isinstance(focused, OptionList):
            focused.action_cursor_down()

    def action_vim_up(self) -> None:
        focused = self.app.focused
        if isinstance(focused, OptionList):
            focused.action_cursor_up()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_focus_export(self) -> None:
        self.query_one("#format-list", OptionList).focus()

    def action_switch_tab(self, tab_id: str) -> None:
        self.query_one("#stats-tabs", TabbedContent).active = tab_id

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
