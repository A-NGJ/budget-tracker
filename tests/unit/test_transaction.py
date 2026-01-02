from datetime import date
from decimal import Decimal

from budget_tracker.models.transaction import StandardTransaction


class TestTransactionId:
    def test_transaction_id_is_deterministic(self) -> None:
        """Same transaction data produces same ID"""

        t1 = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            subcategory="Groceries",
            amount=Decimal("100.00"),
            source="danske_bank",
            description="Test purchase",
        )
        t2 = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            subcategory="Groceries",
            amount=Decimal("100.00"),
            source="danske_bank",
            description="Test purchase",
        )
        assert t1.transaction_id == t2.transaction_id

    def test_transaction_id_differs_for_different_data(self) -> None:
        """Different transaction data produces different IDs"""
        t1 = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            amount=Decimal("100.00"),
            source="danske_bank",
        )
        t2 = StandardTransaction(
            date=date(2026, 1, 2),  # Different date
            category="Food & Drinks",
            amount=Decimal("100.00"),
            source="danske_bank",
        )
        assert t1.transaction_id != t2.transaction_id

    def test_transaction_id_length(self) -> None:
        """Transaction ID is 16 characters (truncated SHA256)"""
        t = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            amount=Decimal("100.00"),
            source="danske_bank",
        )
        assert len(t.transaction_id) == 16

    def test_transaction_id_handles_none_values(self) -> None:
        """Transaction ID works with None subcategory and description"""
        t = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            subcategory=None,
            amount=Decimal("100.00"),
            source="danske_bank",
            description=None,
        )
        # Should not raise and should produce valid ID
        assert len(t.transaction_id) == 16
