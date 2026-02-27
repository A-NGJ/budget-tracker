from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import gspread
import gspread.exceptions
import pytest

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    CategoryRow,
    MonthRow,
    SourceRow,
    SummaryData,
)
from budget_tracker.config.settings import get_settings
from budget_tracker.exporters.google_sheets_exporter import GoogleSheetsExporter
from budget_tracker.models.transaction import StandardTransaction

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def sample_analytics() -> AnalyticsResult:
    period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
    return AnalyticsResult(
        summary=SummaryData(
            total_transactions=5,
            total_income=Decimal("30000.00"),
            total_expenses=Decimal("-699.50"),
            net=Decimal("29300.50"),
            avg_transaction=Decimal("-174.88"),
            period=period,
        ),
        category_data=[
            CategoryRow(
                category="Car",
                total=Decimal("-350.00"),
                percentage=50.0,
                transaction_count=1,
                subcategories=[],
            ),
            CategoryRow(
                category="Food & Drinks",
                total=Decimal("-325.50"),
                percentage=46.5,
                transaction_count=2,
                subcategories=[],
            ),
        ],
        monthly_data=[
            MonthRow(
                year=2025,
                month=10,
                label="Oct 2025",
                income=Decimal("30000.00"),
                expenses=Decimal("-149.50"),
                net=Decimal("29850.50"),
                transaction_count=3,
            ),
            MonthRow(
                year=2025,
                month=11,
                label="Nov 2025",
                income=Decimal("0"),
                expenses=Decimal("-550.00"),
                net=Decimal("-550.00"),
                transaction_count=2,
            ),
        ],
        source_data=[
            SourceRow(
                source="Danske Bank",
                total_income=Decimal("30000.00"),
                total_expenses=Decimal("-475.50"),
                transaction_count=3,
            ),
        ],
        period=period,
    )


@pytest.fixture()
def mock_client() -> MagicMock:
    with patch(
        "budget_tracker.exporters.google_sheets_exporter.GoogleSheetsClient"
    ) as mock_cls:
        client = mock_cls.return_value
        client._with_retry.side_effect = (
            lambda _op, func, *args, **kwargs: func(*args, **kwargs)
        )
        yield client


@pytest.fixture()
def mock_worksheet() -> MagicMock:
    return MagicMock(spec=gspread.Worksheet)


@pytest.fixture()
def mock_spreadsheet(mock_worksheet: MagicMock) -> MagicMock:
    spreadsheet = MagicMock(spec=gspread.Spreadsheet)
    spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
    spreadsheet.add_worksheet.return_value = mock_worksheet
    return spreadsheet


def _make_exporter(
    analytics: AnalyticsResult,
    sheet_name: str = "Budget",
) -> GoogleSheetsExporter:
    """Create an exporter with mocked client (mock_client fixture must be active)."""
    return GoogleSheetsExporter(
        get_settings(), analytics_result=analytics, sheet_name=sheet_name
    )


# ── Constructor ───────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestConstructor:
    def test_accepts_analytics_result(
        self, sample_analytics: AnalyticsResult
    ) -> None:
        exporter = _make_exporter(sample_analytics)
        assert exporter.analytics is sample_analytics

    def test_accepts_sheet_name(
        self, sample_analytics: AnalyticsResult
    ) -> None:
        exporter = _make_exporter(sample_analytics, sheet_name="Q1 2025")
        assert exporter.sheet_name == "Q1 2025"

    def test_default_sheet_name(
        self, sample_analytics: AnalyticsResult
    ) -> None:
        exporter = _make_exporter(sample_analytics)
        assert exporter.sheet_name == "Budget"


# ── Summary Sheet ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestWriteSummarySheet:
    def test_creates_worksheet(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_summary_sheet(mock_spreadsheet)
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="Summary", rows=200, cols=20
        )

    def test_writes_period_label(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_summary_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[0][0] == "All Time"

    def test_writes_metrics(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_summary_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[2] == ["Total Transactions", 5]
        assert data[3][0] == "Total Income"
        assert data[3][1] == pytest.approx(30000.00)
        assert data[4][0] == "Total Expenses"
        assert data[4][1] == pytest.approx(-699.50)
        assert data[5][0] == "Net"
        assert data[5][1] == pytest.approx(29300.50)
        assert data[6][0] == "Avg Transaction"
        assert data[6][1] == pytest.approx(-174.88)

    def test_applies_formatting(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_summary_sheet(mock_spreadsheet)
        format_ranges = [c[0][0] for c in mock_worksheet.format.call_args_list]
        # Period label bold
        assert "A1" in format_ranges
        # Labels bold
        assert "A3:A7" in format_ranges
        # Money format
        assert "B4:B7" in format_ranges
        # Individual color cells
        assert "B4" in format_ranges  # income green
        assert "B5" in format_ranges  # expenses red
        assert "B6" in format_ranges  # net color-coded
        assert "B7" in format_ranges  # avg red


# ── Category Sheet ────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestWriteCategorySheet:
    def test_creates_worksheet(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_category_sheet(mock_spreadsheet)
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="Categories", rows=200, cols=20
        )

    def test_writes_headers(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_category_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[0] == ["Category", "Amount (DKK)", "% of Total", "# Transactions"]

    def test_writes_category_data(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_category_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        # Car (first category)
        assert data[1][0] == "Car"
        assert data[1][1] == pytest.approx(-350.00)
        assert data[1][2] == pytest.approx(0.5)  # 50% as decimal
        assert data[1][3] == 1
        # Food & Drinks (second)
        assert data[2][0] == "Food & Drinks"
        assert data[2][1] == pytest.approx(-325.50)
        assert data[2][2] == pytest.approx(0.465)  # 46.5% as decimal

    def test_applies_header_formatting(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_category_sheet(mock_spreadsheet)
        format_ranges = [c[0][0] for c in mock_worksheet.format.call_args_list]
        assert "A1:D1" in format_ranges

    def test_applies_money_and_percent_format(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_category_sheet(mock_spreadsheet)
        format_ranges = [c[0][0] for c in mock_worksheet.format.call_args_list]
        assert "B2:B3" in format_ranges  # money + red for 2 categories
        assert "C2:C3" in format_ranges  # percent format


# ── Monthly Sheet ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestWriteMonthlySheet:
    def test_creates_worksheet(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_monthly_sheet(mock_spreadsheet)
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="Monthly", rows=200, cols=20
        )

    def test_writes_headers(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_monthly_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[0] == ["Month", "Income", "Expenses", "Net", "# Transactions"]

    def test_writes_monthly_data(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_monthly_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[1][0] == "Oct 2025"
        assert data[1][1] == pytest.approx(30000.00)
        assert data[1][2] == pytest.approx(-149.50)
        assert data[1][3] == pytest.approx(29850.50)
        assert data[2][0] == "Nov 2025"
        assert data[2][3] == pytest.approx(-550.00)

    def test_applies_income_expense_coloring(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_monthly_sheet(mock_spreadsheet)
        format_ranges = [c[0][0] for c in mock_worksheet.format.call_args_list]
        assert "B2:B3" in format_ranges  # income green
        assert "C2:C3" in format_ranges  # expenses red

    def test_applies_net_color_per_row(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_monthly_sheet(mock_spreadsheet)
        format_calls = {
            c[0][0]: c[0][1] for c in mock_worksheet.format.call_args_list
        }
        # Oct 2025 net is positive → green
        green = {"red": 0, "green": 0.502, "blue": 0}
        red = {"red": 1, "green": 0, "blue": 0}
        assert format_calls["D2"]["textFormat"]["foregroundColor"] == green
        # Nov 2025 net is negative → red
        assert format_calls["D3"]["textFormat"]["foregroundColor"] == red


# ── Source Sheet ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestWriteSourceSheet:
    def test_creates_worksheet(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_source_sheet(mock_spreadsheet)
        mock_spreadsheet.add_worksheet.assert_called_once_with(
            title="Sources", rows=200, cols=20
        )

    def test_writes_headers(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_source_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[0] == ["Source", "Income", "Expenses", "# Transactions"]

    def test_writes_source_data(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_source_sheet(mock_spreadsheet)
        data = mock_worksheet.update.call_args[0][0]
        assert data[1][0] == "Danske Bank"
        assert data[1][1] == pytest.approx(30000.00)
        assert data[1][2] == pytest.approx(-475.50)
        assert data[1][3] == 3

    def test_applies_income_expense_coloring(
        self,
        sample_analytics: AnalyticsResult,
        mock_spreadsheet: MagicMock,
        mock_worksheet: MagicMock,
    ) -> None:
        _make_exporter(sample_analytics)._write_source_sheet(mock_spreadsheet)
        format_ranges = [c[0][0] for c in mock_worksheet.format.call_args_list]
        assert "B2:B2" in format_ranges  # income green (1 source)
        assert "C2:C2" in format_ranges  # expenses red (1 source)


# ── Export Integration ────────────────────────────────────────────────


@pytest.mark.usefixtures("mock_client")
class TestExport:
    @pytest.fixture()
    def _setup_export(self, mock_client: MagicMock) -> MagicMock:
        """Set up mock client for full export tests."""
        spreadsheet = MagicMock()
        worksheet = MagicMock(spec=gspread.Worksheet)
        spreadsheet.sheet1 = worksheet
        spreadsheet.worksheet.side_effect = gspread.exceptions.WorksheetNotFound
        spreadsheet.add_worksheet.return_value = MagicMock(spec=gspread.Worksheet)
        mock_client.open_or_create_spreadsheet.return_value = spreadsheet
        mock_client.get_all_values.return_value = [
            ["Transaction ID", "Date", "Description", "Category",
             "Subcategory", "Amount (DKK)", "Source"],
        ]
        return spreadsheet

    def _sample_transactions(self) -> list[StandardTransaction]:
        return [
            StandardTransaction(
                date=date(2025, 10, 5),
                category="Food & Drinks",
                subcategory="Restaurants",
                amount=Decimal("-100"),
                source="Danske Bank",
                description="Lunch",
            ),
        ]

    def test_uses_sheet_name(
        self,
        sample_analytics: AnalyticsResult,
        mock_client: MagicMock,
        _setup_export: MagicMock,
    ) -> None:
        exporter = _make_exporter(sample_analytics, sheet_name="My Budget")
        exporter.export(self._sample_transactions())
        mock_client.open_or_create_spreadsheet.assert_called_once_with("My Budget")

    def test_creates_four_analytics_worksheets(
        self,
        sample_analytics: AnalyticsResult,
        _setup_export: MagicMock,
    ) -> None:
        spreadsheet = _setup_export
        exporter = _make_exporter(sample_analytics)
        exporter.export(self._sample_transactions())
        titles = [c.kwargs["title"] for c in spreadsheet.add_worksheet.call_args_list]
        assert "Summary" in titles
        assert "Categories" in titles
        assert "Monthly" in titles
        assert "Sources" in titles

    def test_returns_empty_message_for_no_transactions(
        self,
        sample_analytics: AnalyticsResult,
    ) -> None:
        exporter = _make_exporter(sample_analytics)
        result = exporter.export([])
        assert result == "No transactions to export."

    def test_appends_new_transactions(
        self,
        sample_analytics: AnalyticsResult,
        mock_client: MagicMock,
        _setup_export: MagicMock,
    ) -> None:
        exporter = _make_exporter(sample_analytics)
        exporter.export(self._sample_transactions())
        mock_client.append_rows.assert_called_once()

    def test_skips_duplicates(
        self,
        sample_analytics: AnalyticsResult,
        mock_client: MagicMock,
        _setup_export: MagicMock,
    ) -> None:
        txns = self._sample_transactions()
        # Simulate existing transaction ID already in sheet
        mock_client.get_all_values.return_value = [
            ["Transaction ID"],
            [txns[0].transaction_id],
        ]
        exporter = _make_exporter(sample_analytics)
        result = exporter.export(txns)
        mock_client.append_rows.assert_not_called()
        assert "0 added, 1 skipped" in result
