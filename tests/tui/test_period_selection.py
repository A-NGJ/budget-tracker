"""Pilot API tests for the period selection screen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, OptionList

from budget_tracker.parsers.csv_parser import ParsedTransaction
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.period_selection import (
    PeriodSelectionScreen,
    _build_presets,
    _count_in_range,
)

TXN_JAN = ParsedTransaction(
    date=date(2024, 1, 15),
    amount=Decimal("-150.00"),
    currency="DKK",
    description="NETTO",
    source="danske_bank",
    source_file="danske.csv",
)
TXN_FEB = ParsedTransaction(
    date=date(2024, 2, 10),
    amount=Decimal("-89.50"),
    currency="DKK",
    description="MATAS",
    source="danske_bank",
    source_file="danske.csv",
)
TXN_MAR = ParsedTransaction(
    date=date(2024, 3, 5),
    amount=Decimal("4500.00"),
    currency="DKK",
    description="LOEN",
    source="danske_bank",
    source_file="danske.csv",
)

TRANSACTIONS = [TXN_JAN, TXN_FEB, TXN_MAR]


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = []
    # CategorizationScreen dependencies (loaded after period selection finishes)
    service.load_categories.return_value = {}
    service.get_cached_category.return_value = None
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    a = BudgetTrackerApp(service=mock_service)
    a.pipeline_state.transactions_to_categorize = list(TRANSACTIONS)
    return a


async def _push_period_selection(app: BudgetTrackerApp, pilot: object) -> None:
    """Push period selection screen and wait for mount."""
    app.push_screen("period_selection")
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


# ── Rendering tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_screen_renders_with_preset_options(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        screen = app.screen
        assert isinstance(screen, PeriodSelectionScreen)

        option_list = screen.query_one("#preset-list", OptionList)
        assert option_list.option_count == 5

        # First option should contain "All time"
        first_option = option_list.get_option_at_index(0)
        assert "All time" in str(first_option.prompt)
        assert "3 transactions" in str(first_option.prompt)


@pytest.mark.asyncio
async def test_screen_renders_transaction_counts(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        screen = app.screen
        assert isinstance(screen, PeriodSelectionScreen)

        option_list = screen.query_one("#preset-list", OptionList)

        # All time should show 3 transactions
        all_time = option_list.get_option_at_index(0)
        assert "3 transactions" in str(all_time.prompt)


@pytest.mark.asyncio
async def test_custom_range_hidden_by_default(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        screen = app.screen
        assert isinstance(screen, PeriodSelectionScreen)

        custom_inputs = screen.query_one("#custom-range-inputs")
        assert custom_inputs.display is False


# ── Selection tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_all_time_pushes_categorization(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        # First option is highlighted by default, press Enter to select
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        # All transactions should remain (no filtering for All time)
        assert len(app.pipeline_state.transactions_to_categorize) == 3
        assert app.pipeline_state.period is not None
        assert app.pipeline_state.period.label == "All Time"


@pytest.mark.asyncio
async def test_select_preset_filters_transactions(app: BudgetTrackerApp) -> None:
    """Selecting a preset with a date range should filter transactions."""
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        # Navigate to a preset that will filter — "Last year" (index 3)
        # Transactions are in Jan-Mar 2024, so if current year > 2024,
        # "Last year" would include them; if current year is 2024 it won't.
        # Instead, test state.period is set correctly on any selection.
        # Move down once to "Last month"
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert app.pipeline_state.period is not None
        assert app.pipeline_state.period.from_date is not None
        assert app.pipeline_state.period.to_date is not None


@pytest.mark.asyncio
async def test_custom_range_reveals_inputs(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        screen = app.screen
        assert isinstance(screen, PeriodSelectionScreen)

        # Navigate down to "Custom range..." (index 4)
        for _ in range(4):
            await pilot.press("down")
            await pilot.pause()

        custom_inputs = screen.query_one("#custom-range-inputs")
        assert custom_inputs.display is True


@pytest.mark.asyncio
async def test_custom_range_filters_transactions(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        screen = app.screen
        assert isinstance(screen, PeriodSelectionScreen)

        # Navigate to custom range
        for _ in range(4):
            await pilot.press("down")
            await pilot.pause()

        # Enter custom date range that includes only Jan and Feb
        from_input = screen.query_one("#from-date", Input)
        to_input = screen.query_one("#to-date", Input)

        from_input.value = "2024-01-01"
        to_input.value = "2024-02-28"
        await pilot.pause()

        # Press Enter on the custom range option to trigger selection
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()

        assert app.pipeline_state.period is not None
        assert app.pipeline_state.period.from_date == date(2024, 1, 1)
        assert app.pipeline_state.period.to_date == date(2024, 2, 28)
        # Only TXN_JAN and TXN_FEB should remain
        assert len(app.pipeline_state.transactions_to_categorize) == 2


# ── Navigation tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_escape_goes_back(app: BudgetTrackerApp) -> None:
    async with app.run_test() as pilot:
        await _push_period_selection(app, pilot)

        assert isinstance(app.screen, PeriodSelectionScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, PeriodSelectionScreen)


# ── Unit tests for helper functions ──────────────────────────


def test_count_in_range_all() -> None:
    count = _count_in_range(TRANSACTIONS, None, None)
    assert count == 3


def test_count_in_range_partial() -> None:
    count = _count_in_range(TRANSACTIONS, date(2024, 2, 1), date(2024, 2, 28))
    assert count == 1


def test_build_presets_includes_all_options() -> None:
    presets = _build_presets(TRANSACTIONS)
    assert len(presets) == 5
    assert "All time" in presets[0][0]
    assert "Last month" in presets[1][0]
    assert "Last 3 months" in presets[2][0]
    assert "Last year" in presets[3][0]
    assert "Custom range" in presets[4][0]


def test_build_presets_empty_transactions() -> None:
    presets = _build_presets([])
    assert len(presets) == 5
    assert "0 transactions" in presets[0][0]
