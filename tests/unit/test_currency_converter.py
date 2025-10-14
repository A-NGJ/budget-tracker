from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.currency.exchange_rate_provider import ExchangeRateProvider


class TestExchangeRateProvider:
    @pytest.fixture
    def provider(self) -> ExchangeRateProvider:
        return ExchangeRateProvider()

    def test_fetch_rate_for_date(self, provider: ExchangeRateProvider) -> None:
        """Test fetching exchange rate for a specific date"""
        # Mock the API response
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45},
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            rate = provider.get_rate("EUR", "DKK", date(2025, 10, 10))
            assert rate == Decimal("7.45")

    def test_dkk_to_dkk_returns_one(self, provider: ExchangeRateProvider) -> None:
        """Test that DKK to DKK conversion returns 1.0"""
        rate = provider.get_rate("DKK", "DKK", date(2025, 10, 10))
        assert rate == Decimal("1.0")

    def test_cache_rate_to_avoid_repeated_calls(self, provider: ExchangeRateProvider) -> None:
        """Test that rates are cached to avoid redundant API calls"""
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45},
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            # First call
            rate1 = provider.get_rate("EUR", "DKK", date(2025, 10, 10))
            # Second call with same parameters
            rate2 = provider.get_rate("EUR", "DKK", date(2025, 10, 10))

            # API should only be called once
            assert mock_get.call_count == 1
            assert rate1 == rate2

    def test_fallback_on_api_error(self, provider: ExchangeRateProvider) -> None:
        """Test fallback behavior when API is unavailable"""
        import httpx  # noqa: PLC0415

        with patch(
            "budget_tracker.currency.exchange_rate_provider.httpx.get",
            side_effect=httpx.HTTPError("API Error"),
        ), pytest.raises(ValueError, match="Unable to fetch exchange rate"):
            provider.get_rate("EUR", "DKK", date(2025, 10, 10))


class TestCurrencyConverter:
    @pytest.fixture
    def converter(self) -> CurrencyConverter:
        return CurrencyConverter()

    def test_convert_eur_to_dkk(self, converter: CurrencyConverter) -> None:
        """Test converting EUR amount to DKK"""
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45},
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            result = converter.convert(
                amount=Decimal("100.00"),
                from_currency="EUR",
                to_currency="DKK",
                transaction_date=date(2025, 10, 10),
            )

            assert result == Decimal("745.00")

    def test_no_conversion_for_dkk(self, converter: CurrencyConverter) -> None:
        """Test that DKK amounts are not converted"""
        result = converter.convert(
            amount=Decimal("100.00"),
            from_currency="DKK",
            to_currency="DKK",
            transaction_date=date(2025, 10, 10),
        )
        assert result == Decimal("100.00")

    def test_preserve_decimal_precision(self, converter: CurrencyConverter) -> None:
        """Test that decimal precision is maintained"""
        mock_response = {
            "amount": 1.0,
            "base": "USD",
            "date": "2025-10-10",
            "rates": {"DKK": 6.87},
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            result = converter.convert(
                amount=Decimal("123.45"),
                from_currency="USD",
                to_currency="DKK",
                transaction_date=date(2025, 10, 10),
            )

            # 123.45 * 6.87 = 848.1015, rounded to 2 decimals = 848.10
            assert result == Decimal("848.10")
