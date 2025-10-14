"""Unit tests for transaction and bank mapping models."""

from datetime import date
from decimal import Decimal

import pytest

from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.models.transaction import StandardTransaction


class TestStandardTransaction:
    """Tests for StandardTransaction model."""

    def test_create_valid_transaction(self) -> None:
        """Test creating a valid standardized transaction."""
        transaction = StandardTransaction(
            date=date(2025, 10, 10),
            category="Food & Drinks",
            subcategory="Restaurants",
            amount=Decimal("125.50"),
            source="Danske Bank",
        )
        assert transaction.date == date(2025, 10, 10)
        assert transaction.amount == Decimal("125.50")
        assert transaction.category == "Food & Drinks"

    def test_negative_amount_validation(self) -> None:
        """Test that expenses are stored as negative amounts."""
        transaction = StandardTransaction(
            date=date(2025, 10, 10),
            category="Food & Drinks",
            subcategory="Restaurants",
            amount=Decimal("-125.50"),
            source="Danske Bank",
        )
        assert transaction.amount < 0

    def test_empty_category_raises_error(self) -> None:
        """Test that invalid category raises validation error."""
        with pytest.raises(ValueError, match="Category cannot be empty"):
            StandardTransaction(
                date=date(2025, 10, 10),
                category="",
                subcategory="Test",
                amount=Decimal("100"),
                source="Test Bank",
            )

    def test_invalid_category_raises_error(self) -> None:
        """Test that non-existent category raises validation error."""
        with pytest.raises(
            ValueError, match=r"Category 'NonExistent' not found in categories.yaml"
        ):
            StandardTransaction(
                date=date(2025, 10, 10),
                category="NonExistent",
                subcategory="Test",
                amount=Decimal("100"),
                source="Test Bank",
            )

    def test_invalid_subcategory_raises_error(self) -> None:
        """Test that non-existent subcategory raises validation error."""
        with pytest.raises(
            ValueError, match=r"Subcategory 'NonExistent' not found under category 'Food & Drinks'"
        ):
            StandardTransaction(
                date=date(2025, 10, 10),
                category="Food & Drinks",
                subcategory="NonExistent",
                amount=Decimal("100"),
                source="Test Bank",
            )


class TestBankMapping:
    """Tests for BankMapping model."""

    def test_create_bank_mapping(self) -> None:
        """Test creating bank column mapping configuration."""
        mapping = BankMapping(
            bank_name="Danske Bank",
            column_mapping=ColumnMapping(
                date_column="Dato", amount_column="Beløb", description_columns=["Tekst"]
            ),
            date_format="%d-%m-%Y",
        )
        assert mapping.bank_name == "Danske Bank"
        assert mapping.column_mapping.date_column == "Dato"

    def test_to_dict_serialization(self) -> None:
        """Test serializing mapping to dict for JSON storage."""
        mapping = BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Date", amount_column="Amount", description_columns=["Desc"]
            ),
            date_format="%Y-%m-%d",
        )
        data = mapping.model_dump()
        assert data["bank_name"] == "Test Bank"
        assert data["date_format"] == "%Y-%m-%d"
