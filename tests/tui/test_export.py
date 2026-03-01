"""Pilot API tests for the export screen."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from textual.widgets import DataTable, LoadingIndicator, OptionList, Static

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    CategoryRow,
    SummaryData,
)
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.export import ExportScreen

PERIOD = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")

SUMMARY = SummaryData(
    total_transactions=10,
    total_income=Decimal("15000.00"),
    total_expenses=Decimal("-8500.00"),
    net=Decimal("6500.00"),
    avg_transaction=Decimal("-850.00"),
    period=PERIOD,
)

CATEGORY_DATA = [
    CategoryRow(
        category="Food & Drinks",
        total=Decimal("-4000.00"),
        percentage=47.1,
        transaction_count=5,
    ),
    CategoryRow(
        category="Housing",
        total=Decimal("-3000.00"),
        percentage=35.3,
        transaction_count=3,
    ),
    CategoryRow(
        category="Transportation",
        total=Decimal("-1500.00"),
        percentage=17.6,
        transaction_count=2,
    ),
]

ANALYTICS_RESULT = AnalyticsResult(
    summary=SUMMARY,
    category_data=CATEGORY_DATA,
    monthly_data=[],
    source_data=[],
    period=PERIOD,
)


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = []
    service.compute_analytics.return_value = ANALYTICS_RESULT
    service.export_excel.return_value = "/tmp/budget_2024.xlsx"
    service.export_csv.return_value = "/tmp/budget_2024.csv"
    service.export_google_sheets.return_value = "https://docs.google.com/spreadsheets/d/abc"
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    a = BudgetTrackerApp(service=mock_service)
    a.pipeline_state.period = PERIOD
    a.pipeline_state.categorized_transactions = []
    return a


async def _push_export(app: BudgetTrackerApp, pilot: object) -> None:
    """Push export screen and wait for analytics computation."""
    app.push_screen("export")
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


# ── Analytics rendering tests ────────────────────────────────


@pytest.mark.asyncio
async def test_export_screen_computes_analytics_on_mount(
    app: BudgetTrackerApp, mock_service: MagicMock
) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        mock_service.compute_analytics.assert_called_once()
        assert app.pipeline_state.analytics is ANALYTICS_RESULT


@pytest.mark.asyncio
async def test_analytics_summary_shows_correct_values(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        screen = app.screen
        assert isinstance(screen, ExportScreen)

        summary_text = str(screen.query_one("#summary", Static)._Static__content)  # type: ignore[attr-defined]
        assert "15,000.00" in summary_text
        assert "8,500.00" in summary_text
        assert "6,500.00" in summary_text
        assert "10" in summary_text


@pytest.mark.asyncio
async def test_category_table_renders_rows(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        screen = app.screen
        assert isinstance(screen, ExportScreen)

        table = screen.query_one("#category-table", DataTable)
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_loading_hidden_after_computation(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        screen = app.screen
        assert isinstance(screen, ExportScreen)

        loading = screen.query_one("#loading", LoadingIndicator)
        assert loading.display is False


@pytest.mark.asyncio
async def test_format_selector_has_three_options(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        screen = app.screen
        assert isinstance(screen, ExportScreen)

        format_list = screen.query_one("#format-list", OptionList)
        assert format_list.option_count == 3


# ── Export tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_excel_shows_success(app: BudgetTrackerApp, mock_service: MagicMock) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        # First format (Excel) is highlighted, press Enter
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_service.export_excel.assert_called_once()
        result = app.screen.query_one("#export-result", Static)
        assert result.display is True
        result_text = str(result._Static__content)  # type: ignore[attr-defined]
        assert "/tmp/budget_2024.xlsx" in result_text


@pytest.mark.asyncio
async def test_export_csv_shows_success(app: BudgetTrackerApp, mock_service: MagicMock) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        # Navigate to CSV (index 1)
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_service.export_csv.assert_called_once()
        result = app.screen.query_one("#export-result", Static)
        result_text = str(result._Static__content)  # type: ignore[attr-defined]
        assert "/tmp/budget_2024.csv" in result_text


# ── Navigation tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_escape_goes_back(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        assert isinstance(app.screen, ExportScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, ExportScreen)


@pytest.mark.asyncio
async def test_title_shows_period_label(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_export(app, pilot)

        screen = app.screen
        assert isinstance(screen, ExportScreen)

        title_text = str(screen.query_one("#title", Static)._Static__content)  # type: ignore[attr-defined]
        assert "All Time" in title_text
