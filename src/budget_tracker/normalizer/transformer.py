from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.models.transaction import RawTransaction, StandardTransaction


class TransactionNormalizer:
    """Transform raw CSV data into standardized format"""

    def __init__(self) -> None:
        self.currency_converter = CurrencyConverter()

    def normalize(
        self,
        raw: RawTransaction,
        mapping: BankMapping,
        category: str,
        subcategory: str | None = None,
        confidence: float = 1.0,
    ) -> StandardTransaction | None:
        """
        Normalize a raw transaction to standard format.

        Returns None if transaction is invalid and should be skipped.
        """
        try:
            # Parse date
            date_str = raw.data.get(mapping.column_mapping.date_column)
            if not date_str:
                return None
            parsed_date = self._parse_date(date_str, mapping.date_format)

            # Parse amount
            amount_str = raw.data.get(mapping.column_mapping.amount_column)
            if not amount_str:
                return None
            amount = self._parse_amount(amount_str, mapping.decimal_separator)

            # Determine currency and convert to DKK
            if mapping.column_mapping.currency_column:
                currency = raw.data.get(
                    mapping.column_mapping.currency_column, mapping.default_currency
                )
            else:
                currency = mapping.default_currency

            # Convert to DKK if needed
            amount_dkk = self.currency_converter.convert(
                amount=amount,
                from_currency=currency.upper(),
                to_currency="DKK",
                transaction_date=parsed_date,
            )

            # Get description
            description = raw.data.get(mapping.column_mapping.description_column, "")

            return StandardTransaction(
                date=parsed_date,
                category=category,
                subcategory=subcategory,
                amount=amount_dkk,
                source=mapping.bank_name,
                description=description,
                confidence=confidence,
            )
        except (ValueError, InvalidOperation):
            # Log error and skip malformed transaction
            return None

    def _parse_date(self, date_str: str, date_format: str) -> date:
        """Parse date string according to format"""
        # ruff: noqa: DTZ007 - Bank statements contain dates without timezone info
        return datetime.strptime(date_str.strip(), date_format).date()

    def _parse_amount(self, amount_str: str, decimal_separator: str) -> Decimal:
        """Parse amount string handling different decimal separators"""
        # Remove whitespace and thousand separators
        clean_amount = amount_str.strip().replace(" ", "").replace("'", "")

        # Handle comma as decimal separator
        if decimal_separator == ",":
            clean_amount = clean_amount.replace(".", "").replace(",", ".")
        else:
            clean_amount = clean_amount.replace(",", "")

        return Decimal(clean_amount)
