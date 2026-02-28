"""Context-sensitive keybinding help overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType


class HelpOverlay(ModalScreen[None]):
    """Context-sensitive keybinding help overlay."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close help"),
        Binding("question_mark", "dismiss", "Close help"),
    ]

    DEFAULT_CSS = """
    HelpOverlay {
        align: center middle;
    }
    #help-container {
        width: 50;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #help-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, bindings_text: str) -> None:
        super().__init__()
        self._bindings_text = bindings_text

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static("Keyboard Shortcuts", id="help-title")
            yield Static(self._bindings_text, id="help-bindings")
