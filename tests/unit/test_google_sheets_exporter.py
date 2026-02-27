from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import gspread.exceptions
import pytest

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    SummaryData,
)
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
def minimal_analytics() -> AnalyticsResult:
    period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
    return AnalyticsResult(
        summary=SummaryData(
            total_transactions=0,
            total_income=Decimal("0"),
            total_expenses=Decimal("0"),
            net=Decimal("0"),
            avg_transaction=Decimal("0"),
            period=period,
        ),
        category_data=[],
        monthly_data=[],
        source_data=[],
        period=period,
    )


@pytest.fixture
def exporter(
    settings: Settings, minimal_analytics: AnalyticsResult
) -> GoogleSheetsExporter:
    return GoogleSheetsExporter(settings, analytics_result=minimal_analytics)


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


class TestTransactionToRow:
    def test_converts_transaction_to_row(
        self, exporter: GoogleSheetsExporter, sample_transaction: StandardTransaction
    ) -> None:
        """Test transaction to row conversion."""
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
    def test_default_sheet_name(
        self, settings: Settings, minimal_analytics: AnalyticsResult
    ) -> None:
        exporter = GoogleSheetsExporter(settings, analytics_result=minimal_analytics)
        assert exporter.sheet_name == "Budget"

    def test_custom_sheet_name(
        self, settings: Settings, minimal_analytics: AnalyticsResult
    ) -> None:
        exporter = GoogleSheetsExporter(
            settings, analytics_result=minimal_analytics, sheet_name="Q1 2025"
        )
        assert exporter.sheet_name == "Q1 2025"


class TestExport:
    def test_export_empty_list_returns_message(
        self, exporter: GoogleSheetsExporter
    ) -> None:
        """Test exporting empty list."""
        result = exporter.export([])
        assert result == "No transactions to export."

    @patch("budget_tracker.exporters.google_sheets_exporter.GoogleSheetsClient")
    def test_filters_duplicate_transactions(
        self,
        mock_client_class: MagicMock,
        settings: Settings,
        minimal_analytics: AnalyticsResult,
        sample_transaction: StandardTransaction,
    ) -> None:
        """Test that existing transactions are filtered out."""
        mock_client = mock_client_class.return_value
        mock_client._with_retry.side_effect = (
            lambda _op, func, *args, **kwargs: func(*args, **kwargs)
        )
        mock_worksheet = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound

        mock_client.open_or_create_spreadsheet.return_value = mock_spreadsheet
        # Return header + existing transaction ID
        mock_client.get_all_values.return_value = [
            ["Transaction ID", "Date", "Description"],
            [sample_transaction.transaction_id, "2024-01-15", "Existing"],
        ]

        exporter = GoogleSheetsExporter(
            settings, analytics_result=minimal_analytics
        )
        result = exporter.export([sample_transaction])

        # Should skip the duplicate
        assert "0 added" in result
        assert "1 skipped" in result
        mock_client.append_rows.assert_not_called()

    @patch("budget_tracker.exporters.google_sheets_exporter.GoogleSheetsClient")
    def test_export_uses_sheet_name(
        self,
        mock_client_class: MagicMock,
        settings: Settings,
        minimal_analytics: AnalyticsResult,
    ) -> None:
        """Test that export uses self.sheet_name for the spreadsheet."""
        mock_client = mock_client_class.return_value
        mock_client._with_retry.side_effect = (
            lambda _op, func, *args, **kwargs: func(*args, **kwargs)
        )
        mock_worksheet = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
        mock_client.open_or_create_spreadsheet.return_value = mock_spreadsheet
        mock_client.get_all_values.return_value = [SHEET_COLUMNS]

        exporter = GoogleSheetsExporter(
            settings, analytics_result=minimal_analytics, sheet_name="My Budget"
        )
        exporter.export([
            StandardTransaction(
                date=date(2024, 5, 10),
                category="Housing",
                amount=Decimal("200.00"),
                source="Bank",
            ),
        ])

        mock_client.open_or_create_spreadsheet.assert_called_once_with("My Budget")
