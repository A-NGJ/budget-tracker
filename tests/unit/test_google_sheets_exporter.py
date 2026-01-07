from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_tracker.config.settings import Settings
from budget_tracker.exporters.google_sheets_exporter import SHEET_COLUMNS, GoogleSheetsExporter
from budget_tracker.models.transaction import StandardTransaction


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        google_credentials_dir=tmp_path,
        google_credentials_file=tmp_path / "credentials.json",
        google_token_file=tmp_path / "token.json",
    )


@pytest.fixture
def exporter(settings: Settings) -> GoogleSheetsExporter:
    return GoogleSheetsExporter(settings)


@pytest.fixture
def sample_transaction() -> StandardTransaction:
    return StandardTransaction(
        date=date(2024, 1, 15),
        category="Food & Drinks",
        subcategory="Groceries",
        amount=Decimal("150.00"),
        source="Bank A",
        description="Supermarket purchase",
    )


class TestGroupByYear:
    def test_groups_transactions_by_year(self, exporter: GoogleSheetsExporter) -> None:
        """Test that transactions are grouped by year"""
        t2025 = StandardTransaction(
            date=date(2025, 6, 10),
            category="Shopping",
            amount=Decimal("75.00"),
            source="Bank",
        )

        t2026 = StandardTransaction(
            date=date(2026, 3, 5),
            category="Housing",
            amount=Decimal("50.00"),
            source="Bank",
        )

        result = exporter._group_by_year([t2025, t2026])
        assert 2025 in result
        assert 2026 in result
        assert len(result[2025]) == 1
        assert len(result[2026]) == 1


class TestTransactionToRow:
    def test_converts_transaction_to_row(
        self, exporter: GoogleSheetsExporter, sample_transaction: StandardTransaction
    ) -> None:
        """Test transaction to row converstion."""
        row = exporter._transaction_to_row(sample_transaction)

        assert row[0] == sample_transaction.transaction_id
        assert row[1] == "2024-01-15"
        assert row[2] == "Supermarket purchase"
        assert row[3] == "Food & Drinks"
        assert row[4] == "Groceries"
        assert row[5] == "150.00"
        assert row[6] == "Bank A"

    def test_handles_none_values(self, exporter: GoogleSheetsExporter) -> None:
        """Test transaction to row conversion with None values."""
        t = StandardTransaction(
            date=date(2024, 2, 20),
            category="Housing",
            amount=Decimal("100.00"),
            source="Bank B",
            description=None,
            subcategory=None,
        )

        row = exporter._transaction_to_row(t)

        assert row[2] == ""  # Description
        assert row[4] == ""  # Subcategory


class TestSheetName:
    def test_generates_sheet_name(self, exporter: GoogleSheetsExporter) -> None:
        """Test sheet name generation."""
        assert exporter._get_sheet_name(2026) == "Budget 2026"

    def test_custom_prefix(self, settings: Settings) -> None:
        """Test custom sheet name prefix."""
        exporter = GoogleSheetsExporter(settings, sheet_name_prefix="Expenses")
        assert exporter._get_sheet_name(2026) == "Expenses 2026"


class TestExport:
    def test_export_empty_list_returns_message(self, exporter: GoogleSheetsExporter) -> None:
        """Test exporting empty list."""
        result = exporter.export([])
        assert result == "No transactions to export."

    @patch("budget_tracker.exporters.google_sheets_exporter.GoogleSheetsClient")
    def test_filters_duplicate_transactions(
        self,
        mock_client_class: MagicMock,
        settings: Settings,
        sample_transaction: StandardTransaction,
    ) -> None:
        """Test that existing transactions are filtered out."""
        mock_client = mock_client_class.return_value
        mock_worksheet = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = mock_worksheet

        mock_client.open_or_create_spreadsheet.return_value = mock_spreadsheet
        # Return header + existing transaction ID
        mock_client.get_all_values.return_value = [
            ["Transaction ID", "Date", "Description"],
            [sample_transaction.transaction_id, "2024-01-15", "Existing"],
        ]

        exporter = GoogleSheetsExporter(settings)
        result = exporter.export([sample_transaction])

        # Should skip the duplicate
        assert "0 added" in result
        assert "1 skipped" in result
        mock_client.append_rows.assert_not_called()

    @patch("budget_tracker.exporters.google_sheets_exporter.GoogleSheetsClient")
    def test_export_retes_spreadsheet_per_year(
        self,
        mock_client_class: MagicMock,
        settings: Settings,
    ) -> None:
        """Test that separete spreadsheets are created per year"""
        # Setup mocks
        mock_client = mock_client_class.return_value
        mock_worksheet = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_client.open_or_create_spreadsheet.return_value = mock_spreadsheet
        mock_client.get_all_values.return_value = [SHEET_COLUMNS]  # Just header

        exporter = GoogleSheetsExporter(settings)
        exporter._client = mock_client

        transactions = [
            StandardTransaction(
                date=date(2024, 5, 10),
                category="Housing",
                amount=Decimal("200.00"),
                source="Bank",
            ),
            StandardTransaction(
                date=date(2025, 7, 15),
                category="Food & Drinks",
                amount=Decimal("50.00"),
                source="Bank",
            ),
        ]

        exporter.export(transactions)

        # Should open/create two spreadsheets
        assert mock_client.open_or_create_spreadsheet.call_count == 2
        mock_client.open_or_create_spreadsheet.assert_any_call("Budget 2024")
        mock_client.open_or_create_spreadsheet.assert_any_call("Budget 2025")
