"""Categorization screen for assigning categories to transactions."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, OptionList, Static

from budget_tracker.tui.widgets.category_list import CategoryList
from budget_tracker.tui.widgets.help_overlay import HelpOverlay
from budget_tracker.tui.widgets.transaction_detail import TransactionDetail
from budget_tracker.tui.widgets.transaction_table import TransactionTable

if TYPE_CHECKING:
    from decimal import Decimal

    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.tui.app import BudgetTrackerApp

HELP_TEXT = """\
[b]Categorization[/b]

  [cyan]Enter[/cyan]     Select category
  [cyan]Tab[/cyan]       Switch panel
  [cyan]U[/cyan]         Undo last
  [cyan]S[/cyan]         Skip transaction
  [cyan]/[/cyan]         Search transactions
  [cyan]C[/cyan]         Continue (when done)

[b]Navigation[/b]

  [cyan]↑/↓[/cyan]       Navigate in panel
  [cyan]Tab[/cyan]       Switch panel
  [cyan]Escape[/cyan]    Clear/Back
  [cyan]?[/cyan]         Show this help
"""


class CategorizationScreen(Screen):
    """Split-panel categorization screen."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("tab", "switch_panel", "Next panel", priority=True),
        Binding("shift+tab", "switch_panel_back", "Prev panel", priority=True),
        Binding("j", "vim_down", "Down", show=False),
        Binding("k", "vim_up", "Up", show=False),
        Binding("u", "undo", "Undo", key_display="U"),
        Binding("s", "skip", "Skip", key_display="S"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("c", "continue_action", "Continue", key_display="C"),
        Binding("escape", "escape_action", "Back/Clear"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    CSS_PATH = "../styles/categorization.tcss"

    def __init__(self) -> None:
        super().__init__()
        self._transactions: list = []
        self._categories: dict[str, list[str]] = {}
        self._statuses: list[str] = []
        self._assigned: dict[int, tuple[str, str | None]] = {}
        self._amounts_dkk: dict[int, Decimal] = {}
        self._undo_stack: list[tuple[int, str, tuple[str, str | None] | None]] = []
        self._current_index: int = 0
        self._search_active: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-panels"):
            yield TransactionTable()
            yield CategoryList()
        yield TransactionDetail()
        yield Input(placeholder="Search transactions...", id="search-input")
        yield Static("0/0 categorized", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._categories = self.app.service.load_categories()
        self._transactions = list(self.app.pipeline_state.transactions_to_categorize)
        self._statuses = ["pending"] * len(self._transactions)

        if not self._transactions:
            self._finish()
            return

        self.query_one(TransactionTable).load_transactions(self._transactions)
        self.query_one(CategoryList).load_categories(self._categories)
        self.query_one(OptionList).focus()
        self._auto_apply_cache()
        self._update_status_bar()
        self._update_detail()

    @work(thread=True)
    def _auto_apply_cache(self) -> None:
        applied: list[tuple[int, str, str | None]] = []
        amounts: dict[int, Decimal] = {}

        for i, txn in enumerate(self._transactions):
            cached = self.app.service.get_cached_category(txn.description)
            if cached:
                cat, subcat = cached
                applied.append((i, cat, subcat))

            if txn.currency != "DKK":
                amounts[i] = self.app.service.convert_currency(txn.amount, txn.currency, txn.date)
            else:
                amounts[i] = txn.amount

        self.app.call_from_thread(self._on_cache_applied, applied, amounts)

    def _on_cache_applied(
        self,
        applied: list[tuple[int, str, str | None]],
        amounts: dict[int, Decimal],
    ) -> None:
        self._amounts_dkk.update(amounts)
        txn_table = self.query_one(TransactionTable)

        for i, cat, subcat in applied:
            if self._statuses[i] == "pending":
                self._statuses[i] = "cached"
                self._assigned[i] = (cat, subcat)
                txn_table.update_status(i, "cached")

        self._update_status_bar()
        self._update_detail()

    # ── Event handlers ───────────────────────────────────────

    def on_transaction_table_selected(self, event: TransactionTable.Selected) -> None:
        self._current_index = event.index
        self._update_detail()

    def on_category_list_category_selected(self, event: CategoryList.CategorySelected) -> None:
        idx = self._current_index
        if idx < 0 or idx >= len(self._transactions):
            return

        # Push undo state
        old_status = self._statuses[idx]
        old_assignment = self._assigned.get(idx)
        self._undo_stack.append((idx, old_status, old_assignment))

        # Assign category
        self._statuses[idx] = "done"
        self._assigned[idx] = (event.category, event.subcategory)

        txn_table = self.query_one(TransactionTable)
        txn_table.update_status(idx, "done")

        # Cache progressively
        txn = self._transactions[idx]
        self.app.service.cache_category(txn.description, event.category, event.subcategory)
        self.app.service.save_cache()

        # Convert currency if not yet done
        if idx not in self._amounts_dkk:
            self._convert_currency(idx)

        # Auto-advance to next uncategorized
        if not txn_table.move_to_next_uncategorized():
            self._check_completion()

        self._update_status_bar()
        self._update_detail()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            query = event.value.strip() or None
            self.query_one(TransactionTable).set_filter(query)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._close_search()

    # ── Actions ──────────────────────────────────────────────

    def action_switch_panel(self) -> None:
        if isinstance(self.app.focused, OptionList):
            self.query_one(DataTable).focus()
        else:
            self.query_one(OptionList).focus()

    def action_switch_panel_back(self) -> None:
        self.action_switch_panel()

    def action_vim_down(self) -> None:
        focused = self.app.focused
        if isinstance(focused, (DataTable, OptionList)):
            focused.action_cursor_down()

    def action_vim_up(self) -> None:
        focused = self.app.focused
        if isinstance(focused, (DataTable, OptionList)):
            focused.action_cursor_up()

    def action_undo(self) -> None:
        if not self._undo_stack:
            return
        idx, old_status, old_assignment = self._undo_stack.pop()
        self._statuses[idx] = old_status
        if old_assignment:
            self._assigned[idx] = old_assignment
        elif idx in self._assigned:
            del self._assigned[idx]

        txn_table = self.query_one(TransactionTable)
        txn_table.update_status(idx, old_status)
        txn_table.move_to(idx)

        self._current_index = idx
        self._update_status_bar()
        self._update_detail()

    def action_skip(self) -> None:
        idx = self._current_index
        if idx < 0 or idx >= len(self._transactions):
            return

        old_status = self._statuses[idx]
        old_assignment = self._assigned.get(idx)
        self._undo_stack.append((idx, old_status, old_assignment))

        self._statuses[idx] = "skipped"

        txn_table = self.query_one(TransactionTable)
        txn_table.update_status(idx, "skipped")

        if not txn_table.move_to_next_uncategorized():
            self._check_completion()

        self._update_status_bar()
        self._update_detail()

    def action_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.display = True
        search_input.focus()
        self._search_active = True

    def action_continue_action(self) -> None:
        if self._all_processed():
            self._finish()

    def action_escape_action(self) -> None:
        if self._search_active:
            self._close_search()
            self.query_one(TransactionTable).set_filter(None)
            self.query_one(OptionList).focus()
        elif self.query_one(CategoryList).is_in_subcategory_mode():
            self.query_one(CategoryList).back_to_categories()
        elif any(s != "pending" for s in self._statuses):
            self.app.push_screen(
                ConfirmExitScreen(),
                callback=self._on_confirm_exit,
            )
        else:
            self.app.pop_screen()

    def _on_confirm_exit(self, confirmed: bool | None, /) -> None:
        if confirmed:
            self.app.pop_screen()

    def action_help(self) -> None:
        self.app.push_screen(HelpOverlay(HELP_TEXT))

    # ── Internal ─────────────────────────────────────────────

    @work(thread=True)
    def _convert_currency(self, index: int) -> None:
        txn = self._transactions[index]
        amount_dkk = self.app.service.convert_currency(txn.amount, txn.currency, txn.date)
        self.app.call_from_thread(self._on_currency_converted, index, amount_dkk)

    def _on_currency_converted(self, index: int, amount_dkk: Decimal) -> None:
        self._amounts_dkk[index] = amount_dkk

    def _close_search(self) -> None:
        self.query_one("#search-input", Input).display = False
        self._search_active = False

    def _update_detail(self) -> None:
        idx = self._current_index
        if 0 <= idx < len(self._transactions):
            txn = self._transactions[idx]
            status = self._statuses[idx]
            assignment = self._assigned.get(idx)
            cat = assignment[0] if assignment else None
            subcat = assignment[1] if assignment else None
            self.query_one(TransactionDetail).show_transaction(txn, status, cat, subcat)

    def _update_status_bar(self) -> None:
        categorized = sum(1 for s in self._statuses if s in ("done", "cached"))
        total = len(self._statuses)
        status_text = f"{categorized}/{total} categorized"
        if self._all_processed():
            status_text += "  — Press [bold cyan]C[/bold cyan] to continue"
        self.query_one("#status-bar", Static).update(status_text)

    def _all_processed(self) -> bool:
        return bool(self._statuses) and all(
            s in ("done", "cached", "skipped") for s in self._statuses
        )

    def _check_completion(self) -> None:
        self._update_status_bar()

    def _finish(self) -> None:
        categorized = []
        for i, txn in enumerate(self._transactions):
            if self._statuses[i] in ("done", "cached"):
                cat, subcat = self._assigned[i]
                amount_dkk = self._amounts_dkk.get(i, txn.amount)
                std_txn = self.app.service.create_transaction(txn, cat, subcat, amount_dkk)
                categorized.append(std_txn)

        self.app.pipeline_state.categorized_transactions = categorized
        self.app.push_screen("placeholder")


class ConfirmExitScreen(Screen[bool]):
    """Confirmation dialog for exiting categorization with partial progress."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm_exit", "Yes"),
        Binding("n", "cancel_exit", "No"),
        Binding("escape", "cancel_exit", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmExitScreen {
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
            yield Static("Discard Progress?", id="confirm-title")
            yield Static("You have partially categorized transactions.")
            yield Static("Discard progress and go back?")
            yield Static("")
            yield Static("  [bold cyan]\\[Y][/] Yes   [bold cyan]\\[N][/] No")

    def action_confirm_exit(self) -> None:
        self.dismiss(True)

    def action_cancel_exit(self) -> None:
        self.dismiss(False)
