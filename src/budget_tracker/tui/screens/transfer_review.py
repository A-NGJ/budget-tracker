"""Transfer review screen for confirming detected transfer pairs."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, LoadingIndicator, Static

from budget_tracker.tui.widgets.help_overlay import HelpOverlay

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.binding import BindingType

    from budget_tracker.filters.transfer_detector import TransferPair
    from budget_tracker.parsers.csv_parser import ParsedTransaction
    from budget_tracker.tui.app import BudgetTrackerApp


HELP_TEXT = """\
[b]Transfer Review[/b]

  [cyan]Y[/cyan]  Confirm as internal transfer
  [cyan]N[/cyan]  Reject (categorize normally)
  [cyan]A[/cyan]  Accept all remaining pairs
  [cyan]S[/cyan]  Skip all remaining pairs

[b]Navigation[/b]

  [cyan]?[/cyan]      Show this help
  [cyan]Escape[/cyan] Go back to home
"""


class TransferReviewScreen(Screen):
    """Review detected transfer pairs one at a time."""

    app: BudgetTrackerApp

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("y", "confirm", "Yes", key_display="Y"),
        Binding("n", "reject", "No", key_display="N"),
        Binding("a", "accept_all", "Accept all", key_display="A"),
        Binding("s", "skip_all", "Skip all", key_display="S"),
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "help", "Help", key_display="?"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._pairs: list[TransferPair] = []
        self._remaining: list[ParsedTransaction] = []
        self._confirmed: list[TransferPair] = []
        self._rejected: list[TransferPair] = []
        self._current_index: int = 0
        self._loaded: bool = False

    def compose(self) -> ComposeResult:
        yield Static("Transfer Detection", id="title")
        yield LoadingIndicator(id="loading")
        yield Static("", id="pair-counter")
        yield Vertical(id="pair-card")
        yield Static("Mark as internal transfer?", id="prompt")
        yield Static(
            "  [bold cyan]\\[Y][/] Yes   [bold cyan]\\[N][/] No   "
            "[bold cyan]\\[A][/] Accept all   [bold cyan]\\[S][/] Skip all",
            id="action-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._show_loading(True)
        self._hide_review_ui()
        self._detect_transfers()

    def _show_loading(self, visible: bool) -> None:
        self.query_one("#loading", LoadingIndicator).display = visible

    def _hide_review_ui(self) -> None:
        self.query_one("#pair-counter").display = False
        self.query_one("#pair-card").display = False
        self.query_one("#prompt").display = False
        self.query_one("#action-bar").display = False

    def _show_review_ui(self) -> None:
        self.query_one("#pair-counter").display = True
        self.query_one("#pair-card").display = True
        self.query_one("#prompt").display = True
        self.query_one("#action-bar").display = True

    @work(thread=True)
    def _detect_transfers(self) -> None:
        state = self.app.pipeline_state
        pairs, remaining = self.app.service.detect_transfers(state.parsed_transactions)
        self.app.call_from_thread(self._on_transfers_detected, pairs, remaining)

    def _on_transfers_detected(
        self,
        pairs: list[TransferPair],
        remaining: list[ParsedTransaction],
    ) -> None:
        self._pairs = pairs
        self._remaining = remaining
        self._loaded = True
        self._show_loading(False)

        if not pairs:
            self._finish()
            return

        title = self.query_one("#title", Static)
        title.update(f"Transfer Detection — {len(pairs)} pair(s) found")
        self._show_review_ui()
        self._render_current_pair()

    def _render_current_pair(self) -> None:
        pair = self._pairs[self._current_index]
        total = len(self._pairs)

        counter = self.query_one("#pair-counter", Static)
        counter.update(f"Pair {self._current_index + 1} of {total}:")

        card = self.query_one("#pair-card", Vertical)
        card.remove_children()

        out_desc = pair.outgoing.description
        if len(out_desc) > 40:
            out_desc = out_desc[:40] + "..."
        in_desc = pair.incoming.description
        if len(in_desc) > 40:
            in_desc = in_desc[:40] + "..."

        out_line = (
            f"  [bold red]OUT[/]  {pair.outgoing.date}  "
            f"[red]{pair.outgoing.amount:.2f} {pair.outgoing.currency}[/]  "
            f"{pair.outgoing.source}"
        )
        out_desc_line = f"       {out_desc}"
        in_line = (
            f"  [bold green]IN [/]  {pair.incoming.date}  "
            f"[green]+{pair.incoming.amount:.2f} {pair.incoming.currency}[/]  "
            f"{pair.incoming.source}"
        )
        in_desc_line = f"       {in_desc}"

        card.mount(Static(out_line, classes="transfer-out"))
        card.mount(Static(out_desc_line, classes="transfer-out-desc"))
        card.mount(Static(in_line, classes="transfer-in"))
        card.mount(Static(in_desc_line, classes="transfer-in-desc"))

    def action_confirm(self) -> None:
        if not self._loaded or not self._pairs:
            return
        self._confirmed.append(self._pairs[self._current_index])
        self._advance()

    def action_reject(self) -> None:
        if not self._loaded or not self._pairs:
            return
        self._rejected.append(self._pairs[self._current_index])
        self._advance()

    def action_accept_all(self) -> None:
        if not self._loaded or not self._pairs:
            return
        self._confirmed.extend(self._pairs[self._current_index :])
        self._finish()

    def action_skip_all(self) -> None:
        if not self._loaded or not self._pairs:
            return
        self._rejected.extend(self._pairs[self._current_index :])
        self._finish()

    def _advance(self) -> None:
        self._current_index += 1
        if self._current_index >= len(self._pairs):
            self._finish()
        else:
            self._render_current_pair()

    def _finish(self) -> None:
        state = self.app.pipeline_state
        state.transfer_pairs = list(self._pairs)
        state.confirmed_transfers = list(self._confirmed)
        state.rejected_transfers = list(self._rejected)

        # Transactions to categorize = non-transfer transactions + rejected pair transactions
        rejected_txns: list[ParsedTransaction] = []
        for pair in self._rejected:
            rejected_txns.append(pair.outgoing)
            rejected_txns.append(pair.incoming)
        state.transactions_to_categorize = list(self._remaining) + rejected_txns

        self.app.push_screen("placeholder")

    def action_go_back(self) -> None:
        if self._confirmed or self._rejected:
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


class ConfirmExitScreen(Screen[bool]):
    """Confirmation dialog for exiting transfer review with partial progress."""

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
            yield Static("You have partially reviewed transfers.")
            yield Static("Discard progress and go back?")
            yield Static("")
            yield Static("  [bold cyan]\\[Y][/] Yes   [bold cyan]\\[N][/] No")

    def action_confirm_exit(self) -> None:
        self.dismiss(True)

    def action_cancel_exit(self) -> None:
        self.dismiss(False)
