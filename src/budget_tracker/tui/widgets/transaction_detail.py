"""TransactionDetail widget for displaying full transaction info."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from budget_tracker.parsers.csv_parser import ParsedTransaction


class TransactionDetail(Widget):
    """Display full details for the selected transaction."""

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-content")

    def show_transaction(
        self,
        txn: ParsedTransaction,
        status: str,
        category: str | None,
        subcategory: str | None,
    ) -> None:
        """Update the detail pane with transaction info."""
        amount = txn.amount
        amount_str = (
            f"[green]+{amount:.2f} {txn.currency}[/green]"
            if amount >= 0
            else f"[red]{amount:.2f} {txn.currency}[/red]"
        )

        cat_display = _format_category_status(status, category, subcategory)
        content = (
            f"[bold]{txn.description}[/bold]  "
            f"{txn.date}  {amount_str}  {txn.source}\n"
            f"Category: {cat_display}"
        )
        self.query_one("#detail-content", Static).update(content)

    def clear(self) -> None:
        """Clear the detail pane."""
        self.query_one("#detail-content", Static).update("")


def _format_category_status(status: str, category: str | None, subcategory: str | None) -> str:
    subcat_suffix = f" > {subcategory}" if subcategory else ""
    labels: dict[str, str] = {
        "done": f"[green]✓ {category}{subcat_suffix}[/green]",
        "cached": f"[yellow]⊘ Cached: {category}{subcat_suffix}[/yellow]",
        "skipped": "[dim]— Skipped[/dim]",
        "pending": "[dim]Pending[/dim]",
    }
    return labels.get(status, "[dim]Pending[/dim]")
