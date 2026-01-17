from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from budget_tracker.cli.transfer_confirmation import confirm_transfers
from budget_tracker.filters.transfer_detector import TransferPair
from budget_tracker.parsers.csv_parser import ParsedTransaction


def make_pair(amount: str = "100") -> TransferPair:
    """Helper to create test transfer pairs."""
    return TransferPair(
        outgoing=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=-Decimal(amount),
            currency="DKK",
            description="Transfer to savings",
            source="bank_a",
            source_file="test.csv",
        ),
        incoming=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=Decimal(amount),
            currency="DKK",
            description="Transfer from checking",
            source="bank_b",
            source_file="test.csv",
        ),
    )


class TestConfirmTransfers:
    """Test for confirm_transfers function"""

    def test_empty_list(self) -> None:
        """Empty list returns empty results."""
        confirmed, rejected = confirm_transfers([])
        assert confirmed == []
        assert rejected == []

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.print")
    def test_confirm_single(self, mock_print: MagicMock, mock_ask: MagicMock) -> None:  # noqa: ARG002
        """Test confirming a single transfer pair."""
        mock_ask.return_value = "y"
        pair = make_pair()

        confirmed, rejected = confirm_transfers([pair])

        assert len(confirmed) == 1
        assert len(rejected) == 0

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.print")
    def test_reject_single(self, mock_print: MagicMock, mock_ask: MagicMock) -> None:  # noqa: ARG002
        """Test rejecting a single transfer pair."""
        mock_ask.return_value = "n"
        pair = make_pair()

        confirmed, rejected = confirm_transfers([pair])

        assert len(confirmed) == 0
        assert len(rejected) == 1

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_accept_all(self, mock_print: MagicMock, mock_ask: MagicMock) -> None:  # noqa: ARG002
        """Accept all remaining transfers."""
        mock_ask.return_value = "a"
        pairs = [make_pair("100"), make_pair("200"), make_pair("300")]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 3
        assert len(rejected) == 0

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_skip_all(self, mock_print: MagicMock, mock_ask: MagicMock) -> None:  # noqa: ARG002
        """Skip all remaining transfers."""
        mock_ask.return_value = "s"
        pairs = [make_pair("100"), make_pair("200"), make_pair("300")]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 0
        assert len(rejected) == 3
