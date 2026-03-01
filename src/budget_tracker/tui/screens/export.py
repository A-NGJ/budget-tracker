"""Export screen for displaying analytics and exporting data."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.analytics.models import AnalyticsResult
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Export[/b]

  [cyan]↑/↓[/cyan]     Select export format
  [cyan]Enter[/cyan]   Export in selected format
  [cyan]Escape[/cyan]  Go back

[b]Formats[/b]

  Excel — .xlsx with analytics sheet
  CSV   — plain transactions
  Google Sheets — cloud spreadsheet
"""

MAX_BAR_WIDTH = 20

EXPORT_FORMATS = [
    ("Excel (.xlsx)", "excel"),
    ("CSV (.csv)", "csv"),
    ("Google Sheets", "google_sheets"),
]


class ExportScreen(Screen):
    """Display analytics and trigger export."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Export", id="title")
        yield LoadingIndicator(id="loading")
        with Vertical(id="analytics-panel"):
            yield Static("", id="summary")
            yield DataTable(id="category-table")
        with Vertical(id="export-section"):
            yield Static("Select export format:", id="format-label")
            yield OptionList(id="format-list")
        yield Static("", id="export-result")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#analytics-panel").display = False
        self.query_one("#export-section").display = False
        self.query_one("#export-result").display = False
        self._compute_analytics()

    @work(thread=True)
    def _compute_analytics(self) -> None:
        state = self.app.pipeline_state
        if state.period is None:
            return

        result = self.app.service.compute_analytics(state.categorized_transactions, state.period)
        self.app.call_from_thread(self._on_analytics_computed, result)

    def _on_analytics_computed(self, result: AnalyticsResult) -> None:
        self.app.pipeline_state.analytics = result
        self.query_one("#loading", LoadingIndicator).display = False

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

        # Setup format selector
        format_list = self.query_one("#format-list", OptionList)
        for label, _ in EXPORT_FORMATS:
            format_list.add_option(Option(label))
        format_list.highlighted = 0

        # Show panels
        self.query_one("#analytics-panel").display = True
        self.query_one("#export-section").display = True

        title = self.query_one("#title", Static)
        title.update(f"Export — {result.period.label}")
        format_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if 0 <= index < len(EXPORT_FORMATS):
            _label, format_key = EXPORT_FORMATS[index]
            self._run_export(format_key)

    @work(thread=True)
    def _run_export(self, format_key: str) -> None:
        state = self.app.pipeline_state
        if state.analytics is None:
            return

        try:
            if format_key == "excel":
                path = self.app.service.export_excel(
                    state.categorized_transactions, state.analytics
                )
            elif format_key == "csv":
                path = self.app.service.export_csv(state.categorized_transactions)
            elif format_key == "google_sheets":
                path = self.app.service.export_google_sheets(
                    state.categorized_transactions, state.analytics
                )
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

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
