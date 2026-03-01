"""TransactionTable widget for displaying and navigating transactions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from budget_tracker.parsers.csv_parser import ParsedTransaction

STATUS_INDICATORS: dict[str, str] = {
    "done": "[green]✓[/green]",
    "current": "[cyan]●[/cyan]",
    "pending": "[dim]○[/dim]",
    "cached": "[yellow]⊘[/yellow]",
    "skipped": "[dim]—[/dim]",
}


class TransactionTable(Widget):
    """Transaction list with status indicators and color-coded amounts."""

    class Selected(Message):
        """Emitted when the highlighted row changes."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self) -> None:
        super().__init__()
        self._transactions: list[ParsedTransaction] = []
        self._statuses: list[str] = []
        self._filter_query: str | None = None
        self._filtered_indices: list[int] = []

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", width=2, key="status")
        table.add_column("Date", width=7, key="date")
        table.add_column("Amount", width=12, key="amount")
        table.add_column("Description", key="desc")

    def load_transactions(self, transactions: list[ParsedTransaction]) -> None:
        """Load transactions into the table."""
        self._transactions = transactions
        self._statuses = ["pending"] * len(transactions)
        self._filter_query = None
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._filtered_indices = []
        for i, txn in enumerate(self._transactions):
            if self._filter_query and self._filter_query.lower() not in txn.description.lower():
                continue
            self._filtered_indices.append(i)
            indicator = STATUS_INDICATORS.get(self._statuses[i], "[dim]○[/dim]")
            date_str = txn.date.strftime("%m-%d")
            amount = txn.amount
            amount_str = (
                f"[green]+{amount:.2f}[/green]" if amount >= 0 else f"[red]{amount:.2f}[/red]"
            )
            table.add_row(indicator, date_str, amount_str, txn.description[:40], key=str(i))

    def update_status(self, index: int, status: str) -> None:
        """Update the status indicator for a transaction at the given original index."""
        self._statuses[index] = status
        if index in self._filtered_indices:
            indicator = STATUS_INDICATORS.get(status, "[dim]○[/dim]")
            table = self.query_one(DataTable)
            table.update_cell(str(index), "status", indicator)

    def get_current_index(self) -> int:
        """Return the original index of the currently highlighted row."""
        if not self._filtered_indices:
            return 0
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row
        if 0 <= cursor_row < len(self._filtered_indices):
            return self._filtered_indices[cursor_row]
        return self._filtered_indices[0]

    def move_to(self, index: int) -> None:
        """Jump to the row with the given original index."""
        if index in self._filtered_indices:
            display_row = self._filtered_indices.index(index)
            table = self.query_one(DataTable)
            table.move_cursor(row=display_row)

    def move_to_next_uncategorized(self) -> bool:
        """Move to the next pending/cached transaction. Returns False if none left."""
        current = self.get_current_index()
        # Search after current first
        for i in range(current + 1, len(self._transactions)):
            if self._statuses[i] in ("pending", "cached") and i in self._filtered_indices:
                self.move_to(i)
                return True
        # Wrap around
        for i in range(current):
            if self._statuses[i] in ("pending", "cached") and i in self._filtered_indices:
                self.move_to(i)
                return True
        return False

    def get_visible_indices(self) -> list[int]:
        """Return the original indices of currently visible rows."""
        return list(self._filtered_indices)

    def set_filter(self, query: str | None) -> None:
        """Filter rows by description match."""
        current_index = self.get_current_index() if self._filtered_indices else 0
        self._filter_query = query
        self._rebuild_table()
        if current_index in self._filtered_indices:
            self.move_to(current_index)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Forward row highlight as TransactionTable.Selected."""
        if self._filtered_indices and 0 <= event.cursor_row < len(self._filtered_indices):
            original_index = self._filtered_indices[event.cursor_row]
            self.post_message(TransactionTable.Selected(original_index))
