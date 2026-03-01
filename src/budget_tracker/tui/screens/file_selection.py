"""File selection screen for the budget tracker TUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Select, Static

from budget_tracker.parsers.csv_parser import CSVParser
from budget_tracker.tui.screens.column_mapping import ColumnMappingScreen
from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.models.bank_mapping import BankMapping


HELP_TEXT = """\
[b]File Selection[/b]

  [cyan]A[/cyan]  Add file to queue
  [cyan]R[/cyan]  Remove last file
  [cyan]Enter[/cyan]  Continue to next step

[b]Navigation[/b]

  [cyan]?[/cyan]      Show this help
  [cyan]Escape[/cyan] Go back to home
"""


@dataclass
class FileEntry:
    """Tracks a file added to the processing queue."""

    path: Path
    bank_name: str
    status: str = "pending"  # pending | parsing | done | error
    error_message: str | None = None


class FileSelectionScreen(Screen):
    """File selection screen for processing bank statements."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("a", "add_file", "Add file", key_display="A"),
        Binding("r", "remove_file", "Remove file", key_display="R"),
        Binding("enter", "continue_pipeline", "Continue"),
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._files: list[FileEntry] = []
        self._bank_options: list[tuple[str, str]] = [("New mapping...", "__new__")]
        self._mappings: dict[str, BankMapping] = {}

    def compose(self) -> ComposeResult:
        yield Static("Process Bank Statements", id="title")
        yield Static("Files to process:", id="file-list-label")
        yield Vertical(id="file-list")
        with Horizontal(id="input-row"):
            yield Input(placeholder="Path to CSV file...", id="file-input")
        with Horizontal(id="bank-row"):
            yield Select(
                self._bank_options,
                id="bank-select",
                prompt="Select bank...",
                allow_blank=True,
            )
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))

    def action_add_file(self) -> None:
        file_input = self.query_one("#file-input", Input)
        bank_select = self.query_one("#bank-select", Select)

        path_str = file_input.value.strip()
        bank_value = bank_select.value

        if not path_str:
            self.notify("Please enter a file path.", severity="warning")
            return

        if bank_value is Select.NULL:
            self.notify("Please select a bank.", severity="warning")
            return

        if bank_value == "__new__":
            path = Path(path_str)
            if not path.exists():
                self.notify(f"File not found: {path}", severity="error")
                return
            try:
                df, columns = CSVParser().parse_file(path)
            except Exception as e:
                self.notify(f"Failed to read file: {e}", severity="error")
                return
            self.app.push_screen(
                ColumnMappingScreen(columns, df),
                callback=self._on_mapping_created,
            )
            return

        entry = FileEntry(path=Path(path_str), bank_name=str(bank_value))
        self._files.append(entry)
        self._refresh_file_list()

        file_input.value = ""
        bank_select.clear()

    def _on_mapping_created(self, mapping: BankMapping | None) -> None:
        """Handle result from ColumnMappingScreen."""
        if mapping is None:
            return
        self._mappings[mapping.bank_name] = mapping
        self._bank_options.insert(-1, (mapping.bank_name, mapping.bank_name))
        bank_select = self.query_one("#bank-select", Select)
        bank_select.set_options(self._bank_options)
        bank_select.value = mapping.bank_name

    def action_remove_file(self) -> None:
        if not self._files:
            self.notify("No files to remove.", severity="warning")
            return

        self._files.pop()
        self._refresh_file_list()

    def action_continue_pipeline(self) -> None:
        if not self._files:
            self.notify("Add at least one file before continuing.", severity="warning")
            return
        self.app.push_screen("placeholder")

    def _refresh_file_list(self) -> None:
        file_list = self.query_one("#file-list", Vertical)
        file_list.remove_children()
        status_icons = {"pending": "○", "parsing": "◌", "done": "✓", "error": "✗"}
        for i, entry in enumerate(self._files, 1):
            icon = status_icons.get(entry.status, "○")
            label = f"  {i}. {icon} {entry.path.name} ({entry.bank_name})"
            if entry.error_message:
                label += f" — {entry.error_message}"
            file_list.mount(Static(label, classes=f"file-entry status-{entry.status}"))
