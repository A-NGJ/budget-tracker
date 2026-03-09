"""Pilot API tests for the statistics screen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from textual.widgets import DataTable, Static, TabbedContent

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    CategoryRow,
    SummaryData,
)
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.stats import StatsScreen

PERIOD = AnalyticsPeriod(from_date=None, to_date=None, label="All time")

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
]

ANALYTICS_RESULT = AnalyticsResult(
    summary=SUMMARY,
    category_data=CATEGORY_DATA,
    monthly_data=[],
    source_data=[],
    period=PERIOD,
)

SAMPLE_TRANSACTIONS = [
    StandardTransaction.model_construct(
        date=date(2025, 1, 15),
        category="Food & Drinks",
        subcategory="Groceries",
        amount=Decimal("-125.50"),
        source="Danske Bank",
        description="Supermarket",
    ),
]


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = []
    service.transaction_count.return_value = 10
    service.get_transaction_sources.return_value = ["Danske Bank", "Nordea"]
    service.get_transaction_categories.return_value = ["Food & Drinks", "Housing"]
    service.get_transaction_subcategories.return_value = ["Groceries", "Restaurants"]
    service.get_filtered_transactions.return_value = SAMPLE_TRANSACTIONS
    service.compute_analytics.return_value = ANALYTICS_RESULT
    service.export_excel.return_value = "/tmp/stats_export.xlsx"
    service.export_csv.return_value = "/tmp/stats_export.csv"
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    return BudgetTrackerApp(service=mock_service)


async def _push_stats(app: BudgetTrackerApp, pilot: object) -> None:
    """Push stats screen and wait for mount."""
    app.push_screen(StatsScreen())
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_stats_screen_renders_with_data(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)

        screen = app.screen
        assert isinstance(screen, StatsScreen)

        summary_text = str(screen.query_one("#summary", Static)._Static__content)  # type: ignore[attr-defined]
        assert "15,000.00" in summary_text
        assert "8,500.00" in summary_text

        table = screen.query_one("#category-table", DataTable)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_stats_screen_empty_state(mock_service: MagicMock) -> None:
    mock_service.transaction_count.return_value = 0
    app = BudgetTrackerApp(service=mock_service)

    async with app.run_test() as pilot:
        await _push_stats(app, pilot)

        screen = app.screen
        assert isinstance(screen, StatsScreen)

        empty = screen.query_one("#empty-state", Static)
        assert empty.display is True

        analytics_panel = screen.query_one("#stats-tabs")
        assert analytics_panel.display is False


@pytest.mark.asyncio
async def test_escape_goes_back(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)
        assert isinstance(app.screen, StatsScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, StatsScreen)


@pytest.mark.asyncio
async def test_help_overlay(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)

        await pilot.press("question_mark")
        await pilot.pause()

        assert app.screen.__class__.__name__ == "HelpOverlay"


@pytest.mark.asyncio
async def test_export_excel(app: BudgetTrackerApp, mock_service: MagicMock) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)

        # Focus export and select Excel
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_service.export_excel.assert_called_once()
        result = app.screen.query_one("#export-result", Static)
        assert result.display is True
        result_text = str(result._Static__content)  # type: ignore[attr-defined]
        assert "/tmp/stats_export.xlsx" in result_text


@pytest.mark.asyncio
async def test_export_csv(app: BudgetTrackerApp, mock_service: MagicMock) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)

        # Focus export, navigate to CSV, select
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        mock_service.export_csv.assert_called_once()
        result = app.screen.query_one("#export-result", Static)
        result_text = str(result._Static__content)  # type: ignore[attr-defined]
        assert "/tmp/stats_export.csv" in result_text


@pytest.mark.asyncio
async def test_tab_switching(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)
        screen = app.screen
        assert isinstance(screen, StatsScreen)

        tabs = screen.query_one("#stats-tabs", TabbedContent)
        assert tabs.active == "tab-overview"

        await pilot.press("2")
        await pilot.pause()
        assert tabs.active == "tab-monthly"

        await pilot.press("3")
        await pilot.pause()
        assert tabs.active == "tab-sources"

        await pilot.press("1")
        await pilot.pause()
        assert tabs.active == "tab-overview"


@pytest.mark.asyncio
async def test_monthly_and_sources_tabs_render(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_stats(app, pilot)
        screen = app.screen
        assert isinstance(screen, StatsScreen)

        monthly = screen.query_one("#monthly-table", DataTable)
        assert monthly.row_count == 0

        source = screen.query_one("#source-table", DataTable)
        assert source.row_count == 0
