from datetime import date
from decimal import Decimal

import httpx


class ExchangeRateProvider:
    """
    Fetch historical exchange rates using Frankfurter API.

    Frankfurter is a free, open-source API for current and historical
    foreign exchange rates published by the European Central Bank.
    https://www.frankfurter.app/
    """

    BASE_URL = "https://api.frankfurter.app"

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, date], Decimal] = {}

    def get_rate(self, from_currency: str, to_currency: str, transaction_date: date) -> Decimal:
        """
        Get exchange rate for a specific date.

        Args:
            from_currency: Source currency code (e.g., "EUR", "USD")
            to_currency: Target currency code (e.g., "DKK")
            transaction_date: Date of the transaction

        Returns:
            Exchange rate as Decimal

        Raises:
            ValueError: If rate cannot be fetched
        """
        # No conversion needed for same currency
        if from_currency == to_currency:
            return Decimal("1.0")

        # Check cache first
        cache_key = (from_currency, to_currency, transaction_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch from API
        try:
            url = f"{self.BASE_URL}/{transaction_date.isoformat()}"
            params = {"from": from_currency, "to": to_currency}

            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            rate = Decimal(str(data["rates"][to_currency]))

            # Cache the result
            self._cache[cache_key] = rate

            return rate

        except httpx.HTTPError as e:
            msg = (
                f"Unable to fetch exchange rate for {from_currency} to {to_currency} "
                f"on {transaction_date}: {e}"
            )
            raise ValueError(msg) from e
        except (KeyError, ValueError) as e:
            msg = (
                f"Unable to fetch exchange rate for {from_currency} to {to_currency} "
                f"on {transaction_date}: Invalid response format"
            )
            raise ValueError(msg) from e

    def clear_cache(self) -> None:
        """Clear the exchange rate cache"""
        self._cache.clear()
