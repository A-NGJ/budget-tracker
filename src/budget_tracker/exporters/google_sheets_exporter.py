from typing import Any

import gspread
from rich.console import Console

from budget_tracker.clients import GoogleSheetsClient
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


class GoogleSheetsExporter:
    """
    Export transactions to Google Sheets.

    Organizes transactions into one sheet per year. Detects and skips
    duplicate transactions based on Transaction ID.
    """

    def __init__(self, settings: Settings, sheet_name_prefix: str = "Budget") -> None:
        """
        Initialize the exporter.

        Args:
            settings: Application settings
            sheet_name_prefix: Prefix for spreadsheet names (e.g., "Budget" -> "Budget 2024")
        """
        self.settings = settings
        self.sheet_name_prefix = sheet_name_prefix
        self._client = GoogleSheetsClient(settings)

    def _get_sheet_name(self, year: int) -> str:
        """Generate spreadsheet name for a year"""
        return f"{self.sheet_name_prefix} {year}"

    def _transaction_to_row(self, t: StandardTransaction) -> list[Any]:
        """Convert transaction to row values"""
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

    def _group_by_year(
        self, transactions: list[StandardTransaction]
    ) -> dict[int, list[StandardTransaction]]:
        """Group transactions by year."""
        by_year: dict[int, list[StandardTransaction]] = {}
        for t in transactions:
            year = t.date.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(t)
        return by_year

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to Google Sheets.

        Creates one spreadsheet per year. Skips transactions that already
        exist based on Transaction ID.

        Args:
            transactions: List of standardized transactions to export

        Returns:
            Summary string of export results
        """
        if not transactions:
            return "No transactions to export."

        # Authenticate
        self._client.authenticate()

        # Group by year
        by_year = self._group_by_year(transactions)

        results: list[str] = []
        total_added = 0
        total_skipped = 0

        for year, year_transactions in sorted(by_year.items()):
            sheet_name = self._get_sheet_name(year)
            console.print(f"\n[cyan]Processing {sheet_name}...[/cyan]")

            # Open or create spreadsheet
            spreadsheet = self._client.open_or_create_spreadsheet(sheet_name)
            worksheet = spreadsheet.sheet1

            # Ensure header exists
            self._ensure_header(worksheet)

            # Get existing transaction IDs
            existing_ids = self._get_existing_transaction_ids(worksheet)

            # Filter out duplicates
            new_transactions = [
                t for t in year_transactions if t.transaction_id not in existing_ids
            ]

            skipped = len(year_transactions) - len(new_transactions)
            total_skipped += skipped

            if skipped > 0:
                console.print(f"[yellow]Skipping[/yellow] {skipped} duplicate transaction(s).")

            if new_transactions:
                # Convert to rows and append
                rows = [self._transaction_to_row(t) for t in new_transactions]
                self._client.append_rows(worksheet, rows)
                total_added += len(new_transactions)
                console.print(
                    f"[green]Added[/green] {len(new_transactions)} transaction(s). "
                    f"to '{sheet_name}''"
                )

            results.append(f"{sheet_name}: {len(new_transactions)} added, {skipped} skipped")

        summary = f"Google Sheets export complete: {total_added} added, {total_skipped} skipped."
        return summary
