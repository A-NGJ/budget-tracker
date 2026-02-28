"""Home screen with keyboard-driven menu navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


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


class HomeScreen(Screen):
    """Main menu screen with keyboard shortcuts."""

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
        self.app.push_screen("placeholder")

    def action_blacklists(self) -> None:
        self.app.push_screen("placeholder")

    def action_mappings(self) -> None:
        self.app.push_screen("placeholder")

    def action_clear_cache(self) -> None:
        self.app.push_screen("placeholder")

    def action_quit(self) -> None:
        self.app.exit()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
