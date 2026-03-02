"""Blacklist management screen for per-bank keyword filtering."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, OptionList, Select, Static

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Blacklist Management[/b]

  [cyan]Delete[/cyan]  Remove highlighted keyword
  Type keyword + click [cyan]Add[/cyan] to add

[b]Navigation[/b]

  [cyan]?[/cyan]      Show this help
  [cyan]Escape[/cyan] Go back to home
"""


class BlacklistScreen(Screen):
    """Manage blacklist keywords per bank."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back"),
        Binding("delete", "remove_keyword", "Remove", key_display="Del"),
        Binding("backspace", "remove_keyword", "Remove", show=False),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_bank: str | None = None
        self._keywords: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("Blacklist Management", id="title")
        yield Static("", id="no-banks-msg")
        with Horizontal(id="bank-row"):
            yield Select[str]([], id="bank-select", prompt="Select bank...", allow_blank=True)
        yield Static("Keywords:", id="keywords-label")
        yield OptionList(id="keyword-list")
        yield Static("[dim](no keywords)[/dim]", id="no-keywords-hint")
        with Horizontal(id="add-row"):
            yield Input(placeholder="Enter keyword to add...", id="keyword-input")
            yield Button("Add", id="add-btn", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#keywords-label").display = False
        self.query_one("#keyword-list").display = False
        self.query_one("#no-keywords-hint").display = False
        self.query_one("#add-row").display = False
        self.query_one("#no-banks-msg").display = False

        banks = self.app.service.list_mappings()
        if not banks:
            self.query_one("#bank-row").display = False
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
        self._current_bank = str(event.value)
        self._keywords = self.app.service.load_bank_blacklist(self._current_bank)
        self.query_one("#keywords-label").display = True
        self.query_one("#keyword-list").display = True
        self.query_one("#add-row").display = True
        self._refresh_keyword_list()

    def _refresh_keyword_list(self) -> None:
        keyword_list = self.query_one("#keyword-list", OptionList)
        keyword_list.clear_options()
        for kw in self._keywords:
            keyword_list.add_option(kw)
        if self._keywords:
            keyword_list.highlighted = 0
        self.query_one("#no-keywords-hint").display = not bool(self._keywords)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._add_keyword()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "keyword-input":
            self._add_keyword()

    def _add_keyword(self) -> None:
        if self._current_bank is None:
            return
        keyword_input = self.query_one("#keyword-input", Input)
        keyword = keyword_input.value.strip()
        if not keyword:
            self.notify("Please enter a keyword.", severity="warning")
            return
        if keyword in self._keywords:
            self.notify(f"'{keyword}' is already in the blacklist.", severity="warning")
            return
        self.app.service.add_blacklist_keyword(self._current_bank, keyword)
        self._keywords = self.app.service.load_bank_blacklist(self._current_bank)
        keyword_input.value = ""
        self._refresh_keyword_list()

    def action_remove_keyword(self) -> None:
        if self._current_bank is None or not self._keywords:
            return
        # Don't remove keywords while typing in the input field
        if self.query_one("#keyword-input", Input).has_focus:
            return
        keyword_list = self.query_one("#keyword-list", OptionList)
        idx = keyword_list.highlighted
        if idx is None:
            return
        keyword = self._keywords[idx]
        self.app.service.remove_blacklist_keyword(self._current_bank, keyword)
        self._keywords = self.app.service.load_bank_blacklist(self._current_bank)
        self._refresh_keyword_list()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))
