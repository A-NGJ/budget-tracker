"""Pilot API tests for the categorization screen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from textual.widgets import DataTable, Input, OptionList, Static

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    SummaryData,
)
from budget_tracker.parsers.csv_parser import ParsedTransaction
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.categorization import CategorizationScreen
from budget_tracker.tui.widgets.category_list import CategoryList
from budget_tracker.tui.widgets.transaction_detail import TransactionDetail
from budget_tracker.tui.widgets.transaction_table import TransactionTable

CATEGORIES: dict[str, list[str]] = {
    "Food & Drinks": ["Groceries", "Restaurants"],
    "Housing": [],
    "Transportation": [],
}

TXN_1 = ParsedTransaction(
    date=date(2024, 1, 15),
    amount=Decimal("-150.00"),
    currency="DKK",
    description="NETTO",
    source="danske_bank",
    source_file="danske.csv",
)
TXN_2 = ParsedTransaction(
    date=date(2024, 1, 16),
    amount=Decimal("-89.50"),
    currency="DKK",
    description="MATAS",
    source="danske_bank",
    source_file="danske.csv",
)
TXN_3 = ParsedTransaction(
    date=date(2024, 1, 17),
    amount=Decimal("4500.00"),
    currency="DKK",
    description="LOEN",
    source="danske_bank",
    source_file="danske.csv",
)

TRANSACTIONS = [TXN_1, TXN_2, TXN_3]


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = []
    service.load_categories.return_value = dict(CATEGORIES)
    service.get_cached_category.return_value = None
    service.cache_category.return_value = None
    service.save_cache.return_value = None
    service.create_transaction.side_effect = lambda *_: MagicMock()
    # ExportScreen dependencies (loaded after categorization finishes)
    _period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
    service.compute_analytics.return_value = AnalyticsResult(
        summary=SummaryData(
            total_transactions=0,
            total_income=Decimal("0"),
            total_expenses=Decimal("0"),
            net=Decimal("0"),
            avg_transaction=Decimal("0"),
            period=_period,
        ),
        category_data=[],
        monthly_data=[],
        source_data=[],
        period=_period,
    )
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    a = BudgetTrackerApp(service=mock_service)
    a.pipeline_state.period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
    a.pipeline_state.transactions_to_categorize = list(TRANSACTIONS)
    return a


async def _push_categorization(app: BudgetTrackerApp, pilot: object) -> None:
    """Push categorization screen and wait for cache worker."""
    app.push_screen("categorization")
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestCategorizationScreenRender:
    """Tests for initial screen rendering."""

    async def test_three_panel_layout(self, app: BudgetTrackerApp) -> None:
        """TransactionTable, CategoryList, and TransactionDetail are all present."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)
            screen.query_one(TransactionTable)
            screen.query_one(CategoryList)
            screen.query_one(TransactionDetail)

    async def test_transactions_displayed(self, app: BudgetTrackerApp) -> None:
        """All transactions are shown in the DataTable."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            table = app.screen.query_one(DataTable)
            assert table.row_count == 3

    async def test_categories_displayed(self, app: BudgetTrackerApp) -> None:
        """All categories are listed in the OptionList."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            opt_list = app.screen.query_one(OptionList)
            assert opt_list.option_count == 3

    async def test_initial_focus_on_categories(self, app: BudgetTrackerApp) -> None:
        """OptionList has focus on mount."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            assert isinstance(app.focused, OptionList)

    async def test_status_bar_shows_count(self, app: BudgetTrackerApp) -> None:
        """Status bar shows '0/3 categorized' initially."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            status = app.screen.query_one("#status-bar", Static)
            content = str(status._Static__content)  # type: ignore[attr-defined]
            assert "0/3 categorized" in content


@pytest.mark.asyncio
class TestCategorizationNavigation:
    """Tests for panel switching."""

    async def test_tab_switches_to_transaction_table(self, app: BudgetTrackerApp) -> None:
        """Tab moves focus from OptionList to DataTable."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            assert isinstance(app.focused, OptionList)

            await pilot.press("tab")
            await pilot.pause()
            assert isinstance(app.focused, DataTable)

    async def test_shift_tab_switches_back(self, app: BudgetTrackerApp) -> None:
        """Shift+Tab switches focus back to OptionList."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)

            await pilot.press("tab")
            await pilot.pause()
            assert isinstance(app.focused, DataTable)

            await pilot.press("shift+tab")
            await pilot.pause()
            assert isinstance(app.focused, OptionList)


@pytest.mark.asyncio
class TestCategorizationAssignment:
    """Tests for category assignment flow."""

    async def test_enter_assigns_category_no_subcategories(self, app: BudgetTrackerApp) -> None:
        """Selecting Housing (no subcategories) assigns immediately."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Navigate to "Housing" (index 1) and select
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            assert screen._statuses[0] == "done"
            assert screen._assigned[0] == ("Housing", None)

    async def test_enter_drills_into_subcategories(self, app: BudgetTrackerApp) -> None:
        """Selecting Food & Drinks shows subcategory list."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen

            # Press Enter on "Food & Drinks" (first option)
            await pilot.press("enter")
            await pilot.pause()

            cat_list = screen.query_one(CategoryList)
            assert cat_list.is_in_subcategory_mode()

            # OptionList should show "← Back", "Groceries", "Restaurants"
            opt_list = screen.query_one(OptionList)
            assert opt_list.option_count == 3

    async def test_back_from_subcategories(self, app: BudgetTrackerApp) -> None:
        """Selecting ← Back returns to category list."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen

            # Drill into subcategories
            await pilot.press("enter")
            await pilot.pause()

            # Select "← Back" (first option, already highlighted)
            await pilot.press("enter")
            await pilot.pause()

            cat_list = screen.query_one(CategoryList)
            assert not cat_list.is_in_subcategory_mode()
            assert screen.query_one(OptionList).option_count == 3

    async def test_subcategory_selected(self, app: BudgetTrackerApp) -> None:
        """Selecting a subcategory assigns category+subcategory."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Drill into "Food & Drinks"
            await pilot.press("enter")
            await pilot.pause()

            # Navigate past "← Back" to "Groceries" and select
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            assert screen._statuses[0] == "done"
            assert screen._assigned[0] == ("Food & Drinks", "Groceries")

    async def test_cache_called_on_assign(
        self, app: BudgetTrackerApp, mock_service: MagicMock
    ) -> None:
        """Service cache and save methods called after assignment."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)

            # Assign "Housing" to first transaction (NETTO)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            mock_service.cache_category.assert_called_with("NETTO", "Housing", None)
            mock_service.save_cache.assert_called()

    async def test_auto_advance_to_next_uncategorized(self, app: BudgetTrackerApp) -> None:
        """After assigning, cursor advances to next uncategorized."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Assign "Housing" to transaction 0
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            # Current index should have advanced to 1
            assert screen._current_index == 1

    async def test_override_cached_category(self) -> None:
        """Cached category can be overridden by re-selecting."""
        service = MagicMock(spec=BudgetService)
        service.list_mappings.return_value = []
        service.load_categories.return_value = dict(CATEGORIES)
        service.get_cached_category.side_effect = lambda desc: (
            ("Food & Drinks", "Groceries") if desc == "NETTO" else None
        )
        service.create_transaction.side_effect = lambda *_: MagicMock()
        app = BudgetTrackerApp(service=service)
        app.pipeline_state.transactions_to_categorize = list(TRANSACTIONS)

        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)
            assert screen._statuses[0] == "cached"

            # Override: navigate to "Housing" and select
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            assert screen._statuses[0] == "done"
            assert screen._assigned[0] == ("Housing", None)


@pytest.mark.asyncio
class TestCategorizationCacheAutoApply:
    """Tests for cache auto-apply on screen load."""

    async def test_cached_categories_applied(self) -> None:
        """Cached categories are auto-applied with 'cached' status."""
        service = MagicMock(spec=BudgetService)
        service.list_mappings.return_value = []
        service.load_categories.return_value = dict(CATEGORIES)
        service.get_cached_category.side_effect = lambda desc: (
            ("Food & Drinks", "Groceries") if desc == "NETTO" else None
        )
        service.create_transaction.side_effect = lambda *_: MagicMock()
        app = BudgetTrackerApp(service=service)
        app.pipeline_state.transactions_to_categorize = list(TRANSACTIONS)

        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)
            assert screen._statuses[0] == "cached"
            assert screen._assigned[0] == ("Food & Drinks", "Groceries")
            assert screen._statuses[1] == "pending"
            assert screen._statuses[2] == "pending"

    async def test_status_bar_reflects_cache(self) -> None:
        """Status bar count includes cached transactions."""
        service = MagicMock(spec=BudgetService)
        service.list_mappings.return_value = []
        service.load_categories.return_value = dict(CATEGORIES)
        service.get_cached_category.side_effect = lambda desc: (
            ("Food & Drinks", "Groceries") if desc == "NETTO" else None
        )
        service.create_transaction.side_effect = lambda *_: MagicMock()
        app = BudgetTrackerApp(service=service)
        app.pipeline_state.transactions_to_categorize = list(TRANSACTIONS)

        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            status = app.screen.query_one("#status-bar", Static)
            content = str(status._Static__content)  # type: ignore[attr-defined]
            assert "1/3 categorized" in content


@pytest.mark.asyncio
class TestCategorizationUndo:
    """Tests for undo functionality."""

    async def test_undo_reverts_last(self, app: BudgetTrackerApp) -> None:
        """Undo reverts the last assignment."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Assign "Housing"
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            assert screen._statuses[0] == "done"

            # Undo
            await pilot.press("u")
            await pilot.pause()

            assert screen._statuses[0] == "pending"
            assert 0 not in screen._assigned
            assert screen._current_index == 0

    async def test_undo_empty_stack_noop(self, app: BudgetTrackerApp) -> None:
        """Undo with empty stack does nothing."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            await pilot.press("u")
            await pilot.pause()

            assert all(s == "pending" for s in screen._statuses)


@pytest.mark.asyncio
class TestCategorizationSkip:
    """Tests for skip functionality."""

    async def test_skip_advances(self, app: BudgetTrackerApp) -> None:
        """Skip marks transaction as skipped and advances."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            await pilot.press("s")
            await pilot.pause()

            assert screen._statuses[0] == "skipped"
            assert screen._current_index == 1

    async def test_skip_counted_in_progress(self, app: BudgetTrackerApp) -> None:
        """Skipping all transactions shows continue prompt."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Skip all 3
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()

            assert all(s == "skipped" for s in screen._statuses)
            status = screen.query_one("#status-bar", Static)
            content = str(status._Static__content)  # type: ignore[attr-defined]
            assert "continue" in content.lower()


@pytest.mark.asyncio
class TestCategorizationSearch:
    """Tests for search/filter functionality."""

    async def test_search_opens_input(self, app: BudgetTrackerApp) -> None:
        """Pressing / opens the search input."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)

            await pilot.press("slash")
            await pilot.pause()

            search_input = app.screen.query_one("#search-input", Input)
            assert search_input.display is True
            assert isinstance(app.focused, Input)

    async def test_search_filters_transactions(self, app: BudgetTrackerApp) -> None:
        """Typing in search filters the transaction table."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)

            await pilot.press("slash")
            await pilot.pause()

            await pilot.press("n", "e", "t")
            await pilot.pause()

            table = app.screen.query_one(DataTable)
            assert table.row_count == 1  # Only "NETTO" matches "net"

    async def test_escape_clears_search(self, app: BudgetTrackerApp) -> None:
        """Escape clears the search filter and hides input."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)

            # Open search and filter
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("n", "e", "t")
            await pilot.pause()
            assert app.screen.query_one(DataTable).row_count == 1

            # Escape clears filter
            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.query_one(DataTable).row_count == 3
            assert app.screen.query_one("#search-input", Input).display is False


@pytest.mark.asyncio
class TestCategorizationCompletion:
    """Tests for completion flow."""

    async def test_continue_prompt_when_all_done(self, app: BudgetTrackerApp) -> None:
        """Continue prompt appears when all transactions are processed."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Assign "Housing" to all 3 transactions
            await pilot.press("down")  # Navigate to "Housing"
            await pilot.press("enter")  # Assign to txn 0
            await pilot.pause()
            await pilot.press("enter")  # Assign to txn 1 (Housing still highlighted)
            await pilot.pause()
            await pilot.press("enter")  # Assign to txn 2
            await pilot.pause()

            status = screen.query_one("#status-bar", Static)
            content = str(status._Static__content)  # type: ignore[attr-defined]
            assert "3/3 categorized" in content
            assert "continue" in content.lower()

    async def test_pipeline_state_populated(self, app: BudgetTrackerApp) -> None:
        """Pipeline state populated with categorized transactions after continue."""
        async with app.run_test() as pilot:
            await _push_categorization(app, pilot)
            screen = app.screen
            assert isinstance(screen, CategorizationScreen)

            # Assign "Housing" to all 3 transactions
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # Press continue
            await pilot.press("c")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ExportScreen"
            assert len(app.pipeline_state.categorized_transactions) == 3
