"""Home screen with keyboard-driven menu navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Home Screen[/b]

  [cyan]P[/cyan]  Process bank statements
  [cyan]B[/cyan]  Manage blacklists
  [cyan]M[/cyan]  View saved mappings
  [cyan]C[/cyan]  Clear category cache
  [cyan]Q[/cyan]  Quit

[b]Global[/b]

  [cyan]?[/cyan]      Show this help
  [cyan]Escape[/cyan] Go back / close
"""


class ConfirmClearCacheScreen(Screen[bool]):
    """Confirmation dialog for clearing the category cache."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmClearCacheScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #confirm-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static("Clear Category Cache?", id="confirm-title")
            yield Static("Delete all saved category mappings?")
            yield Static("Transactions will be re-prompted on next run.")
            yield Static("")
            yield Static("  [bold cyan]\\[Y][/] Yes   [bold cyan]\\[N][/] No")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HomeScreen(Screen):
    """Main menu screen with keyboard shortcuts."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("p", "process", "Process statements", key_display="P"),
        Binding("b", "blacklists", "Manage blacklists", key_display="B"),
        Binding("m", "mappings", "View mappings", key_display="M"),
        Binding("c", "clear_cache", "Clear cache", key_display="C"),
        Binding("q", "quit", "Quit", key_display="Q"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Budget Tracker", id="title")
        yield Static("")
        yield Static("  [bold cyan]\\[P][/]  Process bank statements", classes="menu-item")
        yield Static("  [bold cyan]\\[B][/]  Manage blacklists", classes="menu-item")
        yield Static("  [bold cyan]\\[M][/]  View saved mappings", classes="menu-item")
        yield Static("  [bold cyan]\\[C][/]  Clear category cache", classes="menu-item")
        yield Static("  [bold cyan]\\[Q][/]  Quit", classes="menu-item")
        yield Footer()

    def action_process(self) -> None:
        self.app.push_screen("file_selection")

    def action_blacklists(self) -> None:
        self.app.push_screen("blacklist")

    def action_mappings(self) -> None:
        self.app.push_screen("mappings")

    def action_clear_cache(self) -> None:
        self.app.push_screen(ConfirmClearCacheScreen(), callback=self._on_clear_cache_result)

    def _on_clear_cache_result(self, confirmed: bool | None, /) -> None:
        if confirmed:
            self.app.service.clear_cache()
            self.notify("Category cache cleared.", severity="information")

    def action_quit(self) -> None:
        self.app.exit()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
