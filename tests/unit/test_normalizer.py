from datetime import date
from decimal import Decimal

import pytest

from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.models.transaction import RawTransaction, StandardTransaction
from budget_tracker.normalizer.transformer import TransactionNormalizer


class TestTransactionNormalizer:
    @pytest.fixture
    def normalizer(self) -> TransactionNormalizer:
        return TransactionNormalizer()

    @pytest.fixture
    def sample_mapping(self) -> BankMapping:
        return BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_column="Description",
            ),
            date_format="%d-%m-%Y",
        )

    def test_normalize_simple_transaction(
        self, normalizer: TransactionNormalizer, sample_mapping: BankMapping
    ) -> None:
        """Test normalizing a basic transaction"""
        raw = RawTransaction(
            data={
                "Date": "10-10-2025",
                "Amount": "-125.50",
                "Description": "Cafe Purchase",
            },
            source_file="test.csv",
        )

        # Category will be set by LLM, for now use placeholder
        standard = normalizer.normalize(raw, sample_mapping, category="Food & Drinks")

        assert standard is not None
        assert standard.date == date(2025, 10, 10)
        assert standard.amount == Decimal("-125.50")
        assert standard.source == "Test Bank"
        assert standard.description == "Cafe Purchase"

    def test_parse_various_date_formats(
        self, normalizer: TransactionNormalizer, sample_mapping: BankMapping
    ) -> None:
        """Test parsing different date formats"""
        test_cases = [
            ("10-10-2025", "%d-%m-%Y", date(2025, 10, 10)),
            ("2025-10-10", "%Y-%m-%d", date(2025, 10, 10)),
            ("10/10/2025", "%d/%m/%Y", date(2025, 10, 10)),
        ]

        for date_str, format_str, expected in test_cases:
            sample_mapping.date_format = format_str
            raw = RawTransaction(
                data={"Date": date_str, "Amount": "100", "Description": "Test"},
                source_file="test.csv",
            )
            standard = normalizer.normalize(raw, sample_mapping, category="Other")
            assert standard is not None
            assert standard.date == expected

    def test_parse_amount_with_different_separators(
        self, normalizer: TransactionNormalizer, sample_mapping: BankMapping
    ) -> None:
        """Test parsing amounts with comma/dot separators"""
        test_cases = [
            ("1234.56", ".", Decimal("1234.56")),
            ("1234,56", ",", Decimal("1234.56")),
            ("-1234.56", ".", Decimal("-1234.56")),
        ]

        for amount_str, separator, expected in test_cases:
            sample_mapping.decimal_separator = separator
            raw = RawTransaction(
                data={"Date": "10-10-2025", "Amount": amount_str, "Description": "Test"},
                source_file="test.csv",
            )
            standard = normalizer.normalize(raw, sample_mapping, category="Other")
            assert standard is not None
            assert standard.amount == expected

    def test_handle_missing_optional_fields(
        self, normalizer: TransactionNormalizer, sample_mapping: BankMapping
    ) -> None:
        """Test graceful handling of missing data"""
        raw = RawTransaction(
            data={"Date": "10-10-2025", "Amount": "100", "Description": ""},
            source_file="test.csv",
        )
        standard = normalizer.normalize(raw, sample_mapping, category="Other")
        assert standard is not None
        assert standard.description == "" or standard.description is None

    def test_skip_invalid_transactions(
        self, normalizer: TransactionNormalizer, sample_mapping: BankMapping
    ) -> None:
        """Test that malformed transactions return None"""
        raw = RawTransaction(
            data={"Date": "invalid-date", "Amount": "100", "Description": "Test"},
            source_file="test.csv",
        )
        result = normalizer.normalize(raw, sample_mapping, category="Other")
        assert result is None  # Should skip invalid data
