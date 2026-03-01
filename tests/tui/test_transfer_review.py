"""Pilot API tests for the transfer review screen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from textual.widgets import Static

from budget_tracker.filters.transfer_detector import TransferPair
from budget_tracker.parsers.csv_parser import ParsedTransaction
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.transfer_review import TransferReviewScreen


def _make_pair(
    amount: Decimal,
    out_source: str = "danske_bank",
    in_source: str = "lunar",
    out_desc: str = "OVERFOERSEL TIL LUNAR",
    in_desc: str = "OVERFOERSEL FRA DANSKE",
) -> TransferPair:
    return TransferPair(
        outgoing=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=-amount,
            currency="DKK",
            description=out_desc,
            source=out_source,
            source_file="danske.csv",
        ),
        incoming=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=amount,
            currency="DKK",
            description=in_desc,
            source=in_source,
            source_file="lunar.csv",
        ),
    )


PAIR_1 = _make_pair(Decimal("5000.00"))
PAIR_2 = _make_pair(
    Decimal("2000.00"),
    out_desc="OVERFOERSEL TIL LUNAR 2",
    in_desc="OVERFOERSEL FRA DANSKE 2",
)
NON_TRANSFER = ParsedTransaction(
    date=date(2024, 1, 16),
    amount=Decimal("-50.00"),
    currency="DKK",
    description="Grocery store",
    source="danske_bank",
    source_file="danske.csv",
)


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = []
    service.detect_transfers.return_value = ([PAIR_1, PAIR_2], [NON_TRANSFER])
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    return BudgetTrackerApp(service=mock_service)


async def _push_transfer_review(app: BudgetTrackerApp, pilot: object) -> None:
    """Navigate to the TransferReviewScreen and wait for detection to complete."""
    app.push_screen("transfer_review")
    # Allow the worker thread to complete and UI to update
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestTransferReviewScreen:
    """Tests for the transfer review screen."""

    async def test_screen_renders_with_pairs(self, app: BudgetTrackerApp) -> None:
        """Screen displays pair counter and transfer pair details."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)
            screen = app.screen
            assert isinstance(screen, TransferReviewScreen)

            # Check title shows pair count
            title = screen.query_one("#title", Static)
            assert "2 pair(s) found" in str(title._Static__content)  # type: ignore[attr-defined]

            # Check pair counter
            counter = screen.query_one("#pair-counter", Static)
            assert "Pair 1 of 2" in str(counter._Static__content)  # type: ignore[attr-defined]

            # Check pair card has OUT and IN rows
            card = screen.query_one("#pair-card")
            children = list(card.children)
            assert len(children) == 4  # out_line, out_desc, in_line, in_desc

    async def test_confirm_advances_to_next_pair(self, app: BudgetTrackerApp) -> None:
        """Pressing Y confirms current pair and shows next."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("y")
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, TransferReviewScreen)

            counter = screen.query_one("#pair-counter", Static)
            assert "Pair 2 of 2" in str(counter._Static__content)  # type: ignore[attr-defined]

    async def test_reject_advances_to_next_pair(self, app: BudgetTrackerApp) -> None:
        """Pressing N rejects current pair and shows next."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("n")
            await pilot.pause()

            screen = app.screen
            assert isinstance(screen, TransferReviewScreen)

            counter = screen.query_one("#pair-counter", Static)
            assert "Pair 2 of 2" in str(counter._Static__content)  # type: ignore[attr-defined]

    async def test_accept_all_advances_screen(self, app: BudgetTrackerApp) -> None:
        """Pressing A accepts all remaining pairs and advances to next screen."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("a")
            await pilot.pause()

            # Should have advanced past TransferReviewScreen
            assert app.screen.__class__.__name__ == "PlaceholderScreen"

    async def test_skip_all_advances_screen(self, app: BudgetTrackerApp) -> None:
        """Pressing S skips all remaining pairs and advances to next screen."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("s")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "PlaceholderScreen"

    async def test_state_populated_after_confirm_and_reject(self, app: BudgetTrackerApp) -> None:
        """Pipeline state is correctly populated after confirming and rejecting."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            # Confirm pair 1
            await pilot.press("y")
            await pilot.pause()

            # Reject pair 2
            await pilot.press("n")
            await pilot.pause()

            state = app.pipeline_state
            assert len(state.confirmed_transfers) == 1
            assert state.confirmed_transfers[0] == PAIR_1
            assert len(state.rejected_transfers) == 1
            assert state.rejected_transfers[0] == PAIR_2

            # transactions_to_categorize = non-transfer + rejected pair transactions
            assert (
                len(state.transactions_to_categorize) == 3
            )  # 1 non-transfer + 2 from rejected pair
            assert NON_TRANSFER in state.transactions_to_categorize

    async def test_accept_all_state(self, app: BudgetTrackerApp) -> None:
        """Accept all populates state with all pairs confirmed."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("a")
            await pilot.pause()

            state = app.pipeline_state
            assert len(state.confirmed_transfers) == 2
            assert len(state.rejected_transfers) == 0
            # Only non-transfer transactions go to categorize
            assert len(state.transactions_to_categorize) == 1
            assert state.transactions_to_categorize[0] == NON_TRANSFER

    async def test_escape_returns_home(self, app: BudgetTrackerApp) -> None:
        """Pressing Escape with no progress returns to home screen."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "HomeScreen"


@pytest.mark.asyncio
class TestTransferReviewNoTransfers:
    """Tests for when no transfers are detected."""

    async def test_no_pairs_auto_advances(self) -> None:
        """Screen auto-advances when no transfer pairs are detected."""
        service = MagicMock(spec=BudgetService)
        service.list_mappings.return_value = []
        service.detect_transfers.return_value = ([], [NON_TRANSFER])
        app = BudgetTrackerApp(service=service)

        async with app.run_test() as pilot:
            app.push_screen("transfer_review")
            await pilot.pause()
            await pilot.pause()

            # Should have auto-advanced past TransferReviewScreen
            assert app.screen.__class__.__name__ == "PlaceholderScreen"

            # State should have all transactions in categorize pool
            state = app.pipeline_state
            assert len(state.transactions_to_categorize) == 1
            assert state.transactions_to_categorize[0] == NON_TRANSFER


@pytest.mark.asyncio
class TestTransferReviewEscapeConfirmation:
    """Tests for escape confirmation when partially reviewed."""

    async def test_escape_with_progress_shows_confirmation(self, app: BudgetTrackerApp) -> None:
        """Pressing Escape after reviewing some pairs shows confirmation dialog."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            # Confirm first pair to create progress
            await pilot.press("y")
            await pilot.pause()

            # Escape should show confirmation
            await pilot.press("escape")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ConfirmExitScreen"

    async def test_confirm_exit_returns_home(self, app: BudgetTrackerApp) -> None:
        """Confirming exit from partially reviewed state returns to previous screen."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("y")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            # Confirm exit
            await pilot.press("y")
            await pilot.pause()

            assert app.screen.__class__.__name__ == "HomeScreen"

    async def test_cancel_exit_stays_on_review(self, app: BudgetTrackerApp) -> None:
        """Cancelling exit returns to the transfer review screen."""
        async with app.run_test() as pilot:
            await _push_transfer_review(app, pilot)

            await pilot.press("y")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            # Cancel exit
            await pilot.press("n")
            await pilot.pause()

            assert isinstance(app.screen, TransferReviewScreen)
