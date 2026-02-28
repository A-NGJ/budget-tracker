"""Temporary placeholder screen for unimplemented features."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class PlaceholderScreen(Screen):
    """Temporary placeholder for unimplemented screens."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Coming Soon", id="placeholder-text")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()
