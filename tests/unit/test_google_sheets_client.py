from pathlib import Path
from unittest.mock import MagicMock, patch

import gspread
import pytest

from budget_tracker.clients import GoogleSheetsAuthError, GoogleSheetsClient
from budget_tracker.config.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings with temp credential paths."""
    return Settings(
        google_credentials_dir=tmp_path,
        google_credentials_file=tmp_path / "credentials.json",
        google_token_file=tmp_path / "token.json",
        google_sheets_retry_attempts=3,
        google_sheets_retry_base_delay=0.01,  # Fast retries for tests
    )


@pytest.fixture
def client(settings: Settings) -> GoogleSheetsClient:
    return GoogleSheetsClient(settings)


class TestRetryLogic:
    def test_retry_succeeds_on_second_attempt(self, client: GoogleSheetsClient) -> None:
        """Test that retry succeeds after transient failure"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 500}}
        mock_response.status_code = 500

        mock_func = MagicMock(side_effect=[gspread.exceptions.APIError(mock_response), "success"])

        result = client._with_retry("test operation", mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_exhaust_attempts(self, client: GoogleSheetsClient) -> None:
        """Test that retry raises after all attempts fail."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 500}}
        mock_response.status_code = 500
        error = gspread.exceptions.APIError(mock_response)
        mock_func = MagicMock(side_effect=error)

        with pytest.raises(gspread.exceptions.APIError):
            client._with_retry("test operation", mock_func)

        assert mock_func.call_count == client.retry_attempts

    def test_retry_uses_exponential_backoff(self, client: GoogleSheetsClient) -> None:
        """Test that delays increase exponentially."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 500}}
        mock_response.status_code = 500
        error = gspread.exceptions.APIError(mock_response)
        mock_func = MagicMock(side_effect=error)

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(gspread.exceptions.APIError):
                client._with_retry("test", mock_func)

            # should have slept twice (not after final attempt)
            assert mock_sleep.call_count == client.retry_attempts - 1
            # First delay: base * 2^0 = 0.01
            # Second delay: base * 2^1 = 0.02
            mock_sleep.assert_any_call(0.01)
            mock_sleep.assert_any_call(0.02)


class TestAuthentication:
    def test_authenticate_raises_without_credentials_file(
        self,
        client: GoogleSheetsClient,
    ) -> None:
        """Test error when credentials.json missing"""
        with pytest.raises(GoogleSheetsAuthError, match="credentials not found"):
            client._authenticate_interactive()

    def test_client_property_raises_before_auth(self, client: GoogleSheetsClient) -> None:
        """Test that client property raises before authenticate()"""
        with pytest.raises(GoogleSheetsAuthError, match="Not authenticated"):
            _ = client.client

    def test_load_credentials_returns_none_if_no_token(self, client: GoogleSheetsClient) -> None:
        """Test that missing token file returns None"""
        assert client._load_credentials() is None


class TestSpreadsheetOperations:
    def test_open_or_create_opens_existing(self, client: GoogleSheetsClient) -> None:
        """Test opening existing spreadsheet"""
        mock_spreadsheet = MagicMock()
        mock_gspread_client = MagicMock()
        mock_gspread_client.open.return_value = mock_spreadsheet
        client._client = mock_gspread_client

        result = client.open_or_create_spreadsheet("Budget 2026")

        mock_gspread_client.open.assert_called_once_with("Budget 2026")
        assert result == mock_spreadsheet

    def test_open_or_create_creates_when_not_found(self, client: GoogleSheetsClient) -> None:
        """Test creating spreadsheet when not found"""
        mock_spreadsheet = MagicMock()
        mock_gspread_client = MagicMock()
        mock_gspread_client.open.side_effect = gspread.SpreadsheetNotFound
        mock_gspread_client.create.return_value = mock_spreadsheet
        client._client = mock_gspread_client

        result = client.open_or_create_spreadsheet("Budget 2026")

        mock_gspread_client.create.assert_called_once_with("Budget 2026")
        assert result == mock_spreadsheet
