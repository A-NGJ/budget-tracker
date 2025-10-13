from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from budget_tracker.currency.exchange_rate_provider import ExchangeRateProvider


class CurrencyConverter:
    """Convert transaction amounts to DKK using historical exchange rates"""

    def __init__(self) -> None:
        self.provider = ExchangeRateProvider()

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        transaction_date: date,
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code (typically "DKK")
            transaction_date: Date to use for exchange rate

        Returns:
            Converted amount rounded to 2 decimal places
        """
        # No conversion needed for same currency
        if from_currency == to_currency:
            return amount

        # Get exchange rate for the transaction date
        rate = self.provider.get_rate(from_currency, to_currency, transaction_date)

        # Convert and round to 2 decimal places
        converted = amount * rate
        return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
