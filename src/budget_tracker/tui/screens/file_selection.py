"""File selection screen for the budget tracker TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, LoadingIndicator, Select, Static

from budget_tracker.tui.screens.column_mapping import ColumnMappingScreen
from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.models.bank_mapping import BankMapping
    from budget_tracker.parsers.csv_parser import ParsedTransaction
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]File Selection[/b]

  [cyan]A[/cyan]      Add file to queue
  [cyan]R[/cyan]      Remove last file
  [cyan]Enter[/cyan]  Continue (when file input is empty)

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
    parsed_transactions: list[ParsedTransaction] = field(default_factory=list)


class FileSelectionScreen(Screen):
    """File selection screen for processing bank statements."""

    app: BudgetTrackerApp

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
        yield LoadingIndicator(id="loading")
        with Horizontal(id="input-row"):
            yield Input(placeholder="Path to CSV file...", id="file-input")
        with Horizontal(id="bank-row"):
            yield Select(
                self._bank_options,
                id="bank-select",
                prompt="Select bank...",
                allow_blank=True,
            )
        yield Static(
            "[dim]Enter on empty field to continue[/dim]",
            id="continue-hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#loading", LoadingIndicator).display = False
        self.query_one("#continue-hint").display = False
        saved_banks = self.app.service.list_mappings()
        for bank in saved_banks:
            self._bank_options.insert(-1, (bank, bank))
        if saved_banks:
            bank_select = self.query_one("#bank-select", Select)
            bank_select.set_options(self._bank_options)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter on empty input continues pipeline; otherwise triggers add."""
        if event.input.id == "file-input" and not event.value.strip() and self._files:
            self.action_continue_pipeline()

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

        path = Path(path_str)
        if not path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return

        if bank_value == "__new__":
            try:
                df, columns = self.app.service.detect_columns(path)
            except Exception as e:
                self.notify(f"Failed to read file: {e}", severity="error")
                return
            self.app.push_screen(
                ColumnMappingScreen(columns, df),
                callback=self._on_mapping_created,
            )
            return

        bank_name = str(bank_value)
        mapping = self._mappings.get(bank_name) or self.app.service.load_mapping(bank_name)
        if mapping is None:
            self.notify(f"No mapping found for '{bank_name}'.", severity="error")
            return

        self._mappings[bank_name] = mapping
        entry = FileEntry(path=path, bank_name=bank_name)
        self._files.append(entry)
        self._refresh_file_list()

        file_input.value = ""
        bank_select.clear()

        self._parse_file(entry, mapping)

    def _on_mapping_created(self, mapping: BankMapping | None) -> None:
        """Handle result from ColumnMappingScreen."""
        if mapping is None:
            return
        self.app.service.save_mapping(mapping)
        self._mappings[mapping.bank_name] = mapping
        if not any(v == mapping.bank_name for _, v in self._bank_options if v != "__new__"):
            self._bank_options.insert(-1, (mapping.bank_name, mapping.bank_name))
        bank_select = self.query_one("#bank-select", Select)
        bank_select.set_options(self._bank_options)
        bank_select.value = mapping.bank_name

    @work(thread=True)
    def _parse_file(self, entry: FileEntry, mapping: BankMapping) -> None:
        """Parse a file in a worker thread."""
        entry.status = "parsing"
        self.app.call_from_thread(self._refresh_file_list)
        self.app.call_from_thread(self._show_loading, True)

        try:
            parsed = self.app.service.parse_file(entry.path, mapping)
            entry.parsed_transactions = parsed
            entry.status = "done"
        except Exception as e:
            entry.status = "error"
            entry.error_message = str(e)
            self.app.call_from_thread(
                self.notify, f"Failed to parse {entry.path.name}: {e}", severity="error"
            )

        self.app.call_from_thread(self._show_loading, False)
        self.app.call_from_thread(self._refresh_file_list)

    def _show_loading(self, visible: bool) -> None:
        self.query_one("#loading", LoadingIndicator).display = visible

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

        # Check all files are parsed
        pending = [f for f in self._files if f.status not in ("done", "error")]
        if pending:
            self.notify("Please wait for all files to finish parsing.", severity="warning")
            return

        errors = [f for f in self._files if f.status == "error"]
        if errors:
            self.notify(
                f"{len(errors)} file(s) had errors. Remove them or fix and re-add.",
                severity="warning",
            )
            return

        state = self.app.pipeline_state
        state.files = [f.path for f in self._files]
        state.bank_names = [f.bank_name for f in self._files]
        state.mappings = dict(self._mappings)
        state.parsed_transactions = [txn for f in self._files for txn in f.parsed_transactions]

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
        self.query_one("#continue-hint").display = bool(self._files)
