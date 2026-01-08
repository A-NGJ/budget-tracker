from datetime import date
from decimal import Decimal

from budget_tracker.filters.transfer_detector import TransferDetector, TransferPair
from budget_tracker.parsers.csv_parser import ParsedTransaction


def make_transaction(
    amount: Decimal,
    source: str,
    tx_date: date | None = None,
    description: str = "Test",
) -> ParsedTransaction:
    """Helper to create test transactions."""
    return ParsedTransaction(
        date=tx_date or date(2024, 1, 15),
        amount=amount,
        currency="DKK",
        description=description,
        source=source,
        source_file="test.csv",
    )


class TestTransferDetector:
    """Tests for TransferDetector."""

    def test_detect_simple_transfer(self) -> None:
        """Detect a simple transfer between two banks"""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_b"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 1
        assert len(remaining) == 0
        assert pairs[0].amount == Decimal("100.00")
        assert pairs[0].outgoing.source == "bank_a"
        assert pairs[0].incoming.source == "bank_b"

    def test_no_transfer_same_bank(self) -> None:
        """Don't match transactions from the same bank"""

        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_a"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_no_transfer_different_dates(self) -> None:
        """Don't match transactions on different dates."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a", date(2024, 1, 15)),
            make_transaction(Decimal("100.00"), "bank_b", date(2024, 1, 16)),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_no_transfer_different_amounts(self) -> None:
        """Don't match transactions with different amounts."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("99.00"), "bank_b"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_mixed_transactions(self) -> None:
        """Correctly separate transfers from regular transactions."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),  # Transfer out
            make_transaction(Decimal("100.00"), "bank_b"),  # Transfer in
            make_transaction(Decimal("-50.00"), "bank_a"),  # Regular expense
            make_transaction(Decimal("200.00"), "bank_a"),  # Regular income
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 1
        assert len(remaining) == 2
        assert pairs[0].amount == Decimal("100.00")

    def test_multiple_transfers(self) -> None:
        """Detect multiple transfers correctly."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_b"),
            make_transaction(Decimal("-200.00"), "bank_b"),
            make_transaction(Decimal("200.00"), "bank_c"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 2
        assert len(remaining) == 0

    def test_transfer_pair_amount_property(self) -> None:
        """TransferPair.amount returns absolute value."""
        pair = TransferPair(
            outgoing=make_transaction(Decimal("-150.00"), "bank_a"),
            incoming=make_transaction(Decimal("150.00"), "bank_b"),
        )

        assert pair.amount == Decimal("150.00")
