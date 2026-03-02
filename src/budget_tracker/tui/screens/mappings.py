"""Read-only viewer for saved bank column mappings."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Select, Static

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.models.bank_mapping import BankMapping
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Saved Mappings[/b]

  Select a bank to view its column mapping.

[b]Navigation[/b]

  [cyan]?[/cyan]      Show this help
  [cyan]Escape[/cyan] Go back to home
"""


def _format_mapping(mapping: BankMapping) -> str:
    """Format a BankMapping as Rich markup for display."""
    cm = mapping.column_mapping
    desc_cols = ", ".join(cm.description_columns) or "(none)"
    currency_col = cm.currency_column or f"(none — default: {mapping.default_currency})"
    blacklist = ", ".join(mapping.blacklist_keywords) if mapping.blacklist_keywords else "(none)"

    return (
        f"[bold]{mapping.bank_name}[/bold]\n\n"
        f"[bold]Column Mapping:[/bold]\n"
        f"  Date column:         [cyan]{cm.date_column}[/cyan]\n"
        f"  Amount column:       [cyan]{cm.amount_column}[/cyan]\n"
        f"  Description columns: [cyan]{desc_cols}[/cyan]\n"
        f"  Currency column:     [cyan]{currency_col}[/cyan]\n\n"
        f"[bold]Format:[/bold]\n"
        f"  Date format:         [cyan]{mapping.date_format}[/cyan]\n"
        f"  Decimal separator:   [cyan]{mapping.decimal_separator}[/cyan]\n"
        f"  Default currency:    [cyan]{mapping.default_currency}[/cyan]\n\n"
        f"[bold]Blacklist Keywords:[/bold]\n"
        f"  {blacklist}"
    )


class MappingsScreen(Screen):
    """Read-only viewer for saved bank column mappings."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Saved Mappings", id="title")
        yield Static("", id="no-banks-msg")
        with Horizontal(id="bank-row"):
            yield Select[str]([], id="bank-select", prompt="Select bank...", allow_blank=True)
        yield Static("[dim]Select a bank to view its mapping.[/dim]", id="mapping-details")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#no-banks-msg").display = False

        banks = self.app.service.list_mappings()
        if not banks:
            self.query_one("#bank-row").display = False
            self.query_one("#mapping-details").display = False
            self.query_one("#no-banks-msg").display = True
            self.query_one("#no-banks-msg", Static).update(
                "[yellow]No bank mappings found. Process a bank statement first.[/yellow]"
            )
            return

        options: list[tuple[str, str]] = [(bank, bank) for bank in banks]
        self.query_one("#bank-select", Select).set_options(options)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "bank-select":
            return
        if event.value is Select.NULL:
            return
        bank_name = str(event.value)
        mapping = self.app.service.load_mapping(bank_name)
        details = self.query_one("#mapping-details", Static)
        if mapping is None:
            details.update(f"[red]Failed to load mapping for '{bank_name}'.[/red]")
            return
        details.update(_format_mapping(mapping))

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
