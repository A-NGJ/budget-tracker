from __future__ import annotations

from typing import TYPE_CHECKING, Any

import gspread
import gspread.exceptions
from rich.console import Console

from budget_tracker.clients import GoogleSheetsClient

if TYPE_CHECKING:
    from budget_tracker.analytics.models import AnalyticsResult
    from budget_tracker.config.settings import Settings
    from budget_tracker.models.transaction import StandardTransaction

console = Console()

SHEET_COLUMNS = [
    "Transaction ID",
    "Date",
    "Description",
    "Category",
    "Subcategory",
    "Amount (DKK)",
    "Source",
]

# Google Sheets API color constants
_GREEN = {"red": 0, "green": 0.502, "blue": 0}
_RED = {"red": 1, "green": 0, "blue": 0}
_WHITE = {"red": 1, "green": 1, "blue": 1}
_HEADER_BG = {"red": 0.267, "green": 0.447, "blue": 0.769}  # #4472C4

_HEADER_FORMAT: dict[str, Any] = {
    "backgroundColor": _HEADER_BG,
    "textFormat": {"bold": True, "foregroundColor": _WHITE},
}
_MONEY_FORMAT: dict[str, Any] = {
    "numberFormat": {"type": "NUMBER", "pattern": "#,##0.00"},
}


class GoogleSheetsExporter:
    """
    Export transactions and analytics to Google Sheets.

    Uses a single named spreadsheet. Deduplicates transactions on re-export
    and recalculates analytics worksheets.
    """

    def __init__(
        self,
        settings: Settings,
        analytics_result: AnalyticsResult,
        sheet_name: str = "Budget",
    ) -> None:
        self.sheet_name = sheet_name
        self.analytics = analytics_result
        self._client = GoogleSheetsClient(settings)

    def _transaction_to_row(self, t: StandardTransaction) -> list[Any]:
        """Convert transaction to row values."""
        return [
            t.transaction_id,
            t.date.strftime("%Y-%m-%d"),
            t.description or "",
            t.category,
            t.subcategory or "",
            f"{t.amount:.2f}",
            t.source,
        ]

    def _get_existing_transaction_ids(self, worksheet: gspread.Worksheet) -> set[str]:
        """Get set of transaction IDs already in worksheet."""
        values = self._client.get_all_values(worksheet)
        if len(values) <= 1:  # Empty or only header
            return set()

        # Transaction ID is first column
        return {row[0] for row in values[1:] if row}

    def _ensure_header(self, worksheet: gspread.Worksheet) -> None:
        """Ensure worksheet has header row."""
        values = self._client.get_all_values(worksheet)
        if len(values[0]) == 0:  # Values returns a nested empty list for an empty sheet
            self._client.append_rows(worksheet, [SHEET_COLUMNS])

    # ── Helpers ───────────────────────────────────────────────────────

    def _batch_update(
        self,
        worksheet: gspread.Worksheet,
        range_str: str,
        values: list[list[Any]],
    ) -> None:
        """Batch write cells using gspread v6 API (values first, then range)."""
        self._client._with_retry(
            f"Updating range {range_str}",
            worksheet.update,
            values,
            range_str,
        )

    def _format_cells(
        self,
        worksheet: gspread.Worksheet,
        range_str: str,
        fmt: dict[str, Any],
    ) -> None:
        """Apply formatting to a cell range."""
        self._client._with_retry(
            "Formatting cells",
            worksheet.format,
            range_str,
            fmt,
        )

    def _get_or_replace_worksheet(
        self, spreadsheet: gspread.Spreadsheet, title: str
    ) -> gspread.Worksheet:
        """Delete existing worksheet with title (if any) and create a fresh one."""
        try:
            ws = spreadsheet.worksheet(title)
            spreadsheet.del_worksheet(ws)
        except gspread.exceptions.WorksheetNotFound:
            pass
        return spreadsheet.add_worksheet(title=title, rows=200, cols=20)

    # ── Analytics Worksheets ──────────────────────────────────────────

    def _write_summary_sheet(self, spreadsheet: gspread.Spreadsheet) -> None:
        """Write Summary worksheet with key metrics."""
        ws = self._get_or_replace_worksheet(spreadsheet, "Summary")
        summary = self.analytics.summary

        data: list[list[Any]] = [
            [summary.period.label, ""],
            ["", ""],
            ["Total Transactions", summary.total_transactions],
            ["Total Income", float(summary.total_income)],
            ["Total Expenses", float(summary.total_expenses)],
            ["Net", float(summary.net)],
            ["Avg Transaction", float(summary.avg_transaction)],
        ]
        self._batch_update(ws, "A1", data)

        # Period label — bold, large
        self._format_cells(ws, "A1", {"textFormat": {"bold": True, "fontSize": 14}})
        # Labels bold
        self._format_cells(ws, "A3:A7", {"textFormat": {"bold": True}})
        # Number format for monetary values
        self._format_cells(ws, "B4:B7", _MONEY_FORMAT)
        # Income green
        self._format_cells(
            ws, "B4", {"textFormat": {"foregroundColor": _GREEN, "bold": True}}
        )
        # Expenses red
        self._format_cells(
            ws, "B5", {"textFormat": {"foregroundColor": _RED, "bold": True}}
        )
        # Net color-coded
        net_color = _GREEN if float(summary.net) >= 0 else _RED
        self._format_cells(
            ws, "B6", {"textFormat": {"foregroundColor": net_color, "bold": True}}
        )
        # Avg transaction red
        self._format_cells(
            ws, "B7", {"textFormat": {"foregroundColor": _RED, "bold": True}}
        )

    def _write_category_sheet(self, spreadsheet: gspread.Spreadsheet) -> None:
        """Write Categories worksheet with expense breakdown."""
        ws = self._get_or_replace_worksheet(spreadsheet, "Categories")
        cat_data = self.analytics.category_data

        headers = [["Category", "Amount (DKK)", "% of Total", "# Transactions"]]
        data_rows: list[list[Any]] = [
            [
                cat.category,
                float(cat.total),
                cat.percentage / 100.0,
                cat.transaction_count,
            ]
            for cat in cat_data
        ]
        self._batch_update(ws, "A1", headers + data_rows)

        self._format_cells(ws, "A1:D1", _HEADER_FORMAT)
        if cat_data:
            last_row = len(cat_data) + 1
            # Amount column — red text + money format
            self._format_cells(ws, f"B2:B{last_row}", {
                **_MONEY_FORMAT,
                "textFormat": {"foregroundColor": _RED},
            })
            # Percentage column
            self._format_cells(ws, f"C2:C{last_row}", {
                "numberFormat": {"type": "PERCENT", "pattern": "0.0%"},
            })

    def _write_monthly_sheet(self, spreadsheet: gspread.Spreadsheet) -> None:
        """Write Monthly worksheet with income/expenses/net per month."""
        ws = self._get_or_replace_worksheet(spreadsheet, "Monthly")
        monthly = self.analytics.monthly_data

        headers = [["Month", "Income", "Expenses", "Net", "# Transactions"]]
        data_rows: list[list[Any]] = [
            [
                m.label,
                float(m.income),
                float(m.expenses),
                float(m.net),
                m.transaction_count,
            ]
            for m in monthly
        ]
        self._batch_update(ws, "A1", headers + data_rows)

        self._format_cells(ws, "A1:E1", _HEADER_FORMAT)
        if monthly:
            last_row = len(monthly) + 1
            # Money format for income/expenses/net columns
            self._format_cells(ws, f"B2:D{last_row}", _MONEY_FORMAT)
            # Income green
            self._format_cells(
                ws, f"B2:B{last_row}", {"textFormat": {"foregroundColor": _GREEN}}
            )
            # Expenses red
            self._format_cells(
                ws, f"C2:C{last_row}", {"textFormat": {"foregroundColor": _RED}}
            )
            # Net — per-row color coding
            for i, m in enumerate(monthly, start=2):
                net_color = _GREEN if float(m.net) >= 0 else _RED
                self._format_cells(
                    ws, f"D{i}", {"textFormat": {"foregroundColor": net_color}}
                )

    def _write_source_sheet(self, spreadsheet: gspread.Spreadsheet) -> None:
        """Write Sources worksheet with per-source breakdown."""
        ws = self._get_or_replace_worksheet(spreadsheet, "Sources")
        sources = self.analytics.source_data

        headers = [["Source", "Income", "Expenses", "# Transactions"]]
        data_rows: list[list[Any]] = [
            [
                s.source,
                float(s.total_income),
                float(s.total_expenses),
                s.transaction_count,
            ]
            for s in sources
        ]
        self._batch_update(ws, "A1", headers + data_rows)

        self._format_cells(ws, "A1:D1", _HEADER_FORMAT)
        if sources:
            last_row = len(sources) + 1
            # Money format
            self._format_cells(ws, f"B2:C{last_row}", _MONEY_FORMAT)
            # Income green
            self._format_cells(
                ws, f"B2:B{last_row}", {"textFormat": {"foregroundColor": _GREEN}}
            )
            # Expenses red
            self._format_cells(
                ws, f"C2:C{last_row}", {"textFormat": {"foregroundColor": _RED}}
            )

    # ── Export ─────────────────────────────────────────────────────────

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions and analytics to a single Google Sheets spreadsheet.

        Opens or creates a spreadsheet named self.sheet_name. Deduplicates
        transactions on re-export and recalculates analytics worksheets.

        Args:
            transactions: List of standardized transactions to export

        Returns:
            Summary string of export results
        """
        if not transactions:
            return "No transactions to export."

        self._client.authenticate()
        console.print(f"\n[cyan]Processing {self.sheet_name}...[/cyan]")

        spreadsheet = self._client.open_or_create_spreadsheet(self.sheet_name)
        worksheet = spreadsheet.sheet1

        self._ensure_header(worksheet)
        existing_ids = self._get_existing_transaction_ids(worksheet)

        new_transactions = [
            t for t in transactions if t.transaction_id not in existing_ids
        ]
        skipped = len(transactions) - len(new_transactions)

        if skipped > 0:
            console.print(f"[yellow]Skipping[/yellow] {skipped} duplicate transaction(s).")

        if new_transactions:
            rows = [self._transaction_to_row(t) for t in new_transactions]
            self._client.append_rows(worksheet, rows)
            console.print(
                f"[green]Added[/green] {len(new_transactions)} transaction(s)"
                f" to '{self.sheet_name}'"
            )

        # Write/replace analytics worksheets
        self._write_summary_sheet(spreadsheet)
        self._write_category_sheet(spreadsheet)
        self._write_monthly_sheet(spreadsheet)
        self._write_source_sheet(spreadsheet)

        return (
            f"Google Sheets export complete:"
            f" {len(new_transactions)} added, {skipped} skipped."
        )
