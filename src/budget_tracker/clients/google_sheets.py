"""Google Sheets client with OAuth authentication and retry logic."""

import json
import time
from collections.abc import Callable

import gspread
import gspread.exceptions
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.utils import ValueInputOption
from rich.console import Console

from budget_tracker.config.settings import Settings

type CellValue = str | int | float

console = Console()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsAuthError(Exception):
    """Raised when Google Sheets authentication fails."""


class GoogleSheetsClient:
    """
    Google Sheets client with OAuth2 authentication and retry logic.

    Credentials are stored in ~/.budet-tracker/ and automatically refreshed.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.credentials_dir = settings.google_credentials_dir
        self.credentials_file = settings.google_credentials_file
        self.token_file = settings.google_token_file
        self.retry_attempts = settings.google_sheets_retry_attempts
        self.retry_base_delay = settings.google_sheets_retry_base_delay
        self._client: gspread.Client | None = None

    def _ensure_credentials_dir(self) -> None:
        """Create credentials directory if it doesn't exist."""
        self.credentials_dir.mkdir(parents=True, exist_ok=True)

    def _load_credentials(self) -> Credentials | None:
        """Load existing credentials from token file."""
        if not self.token_file.exists():
            return None

        with self.token_file.open() as f:
            token_data = json.load(f)

        return Credentials.from_authorized_user_info(token_data, SCOPES)

    def _save_credentials(self, credentials: Credentials) -> None:
        """Save credentials to token file."""
        self._ensure_credentials_dir()
        with self.token_file.open("w") as f:
            f.write(credentials.to_json())

    def _refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Refresh expired credentials"""
        try:
            credentials.refresh(Request())
            self._save_credentials(credentials)
            return credentials
        except RefreshError as e:
            # Token is invalid, need to re-authenticate
            self.token_file.unlink(missing_ok=True)
            msg = "Credentials expired and refresh failed. Please re-authenticate."
            raise GoogleSheetsAuthError(msg) from e

    def _authenticate_interactive(self) -> Credentials:
        """Run interactive OAuth flow in browser"""
        if not self.credentials_file.exists():
            msg = (
                f"Google OAuth credentials not found at {self.credentials_file}. "
                "Please download credentials.json from Google Cloud Console."
            )
            raise GoogleSheetsAuthError(msg)

        flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        return credentials

    def authenticate(self) -> None:
        """
        Authenticate with Google Sheets API.

        Uses existing token if valid, refreshes if expired, or runs
        interactive OAuth flow if no valid credentials exist.
        """

        credentials = self._load_credentials()

        if credentials and credentials.valid:
            self._client = gspread.authorize(credentials)
            return

        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials = self._refresh_credentials(credentials)
                self._client = gspread.authorize(credentials)
                return
            except GoogleSheetsAuthError:
                pass  # Fall through to interactive auth

        console.print("[yellow]Google Sheets authentication required.[/yellow]")
        console.print("A browser window will open for you to authorize access.\n")

        credentials = self._authenticate_interactive()
        self._client = gspread.authorize(credentials)
        console.print("[green]✓[/green] Successfully authenticated with Google Sheets")

    def _with_retry[**P, R](
        self, operation: str, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        """
        Execute function with exponential backoff retry.

        Args:
            operation: Description of the operation for error messages

            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result of function call

        Raises:
            Last exception if all retries fail
        """
        last_exception: Exception = Exception("Unknown error")

        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_base_delay * (2**attempt)
                    console.print(
                        f"[yellow]⚠[/yellow] {operation} failed (attempt {attempt + 1}/"
                        f"{self.retry_attempts}), retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

        raise last_exception

    @property
    def client(self) -> gspread.Client:
        """Get authenticated gspread client."""
        if self._client is None:
            msg = "Not authenticated. Call authenticate() first."
            raise GoogleSheetsAuthError(msg)
        return self._client

    def open_or_create_spreadsheet(self, title: str) -> gspread.Spreadsheet:
        """
        Open existing spreadsheet or create new one.

        Args:
            title: Spreadsheet title to find or create

        Returns:
            gspread.Spreadsheet object
        """

        def _open_or_create() -> gspread.Spreadsheet:
            try:
                return self.client.open(title)
            except gspread.exceptions.SpreadsheetNotFound:
                return self.client.create(title)

        return self._with_retry(f"Opening spreadsheet '{title}'", _open_or_create)

    def get_all_values(self, worksheet: gspread.Worksheet) -> list[list[str]]:
        """Get all values from worksheet with retry."""
        return self._with_retry("Fetching worksheet data", worksheet.get_all_values)

    def append_rows(
        self,
        worksheet: gspread.Worksheet,
        rows: list[list[str]],
        value_input_option: ValueInputOption = ValueInputOption.user_entered,
    ) -> None:
        """Append rows to worksheet with retry."""
        self._with_retry(
            f"Appending {len(rows)} rows",
            worksheet.append_rows,
            rows,
            value_input_option=value_input_option,
        )

    def update_cell(
        self, worksheet: gspread.Worksheet, row: int, col: int, value: CellValue
    ) -> None:
        """Update single cell with retry"""
        self._with_retry(
            f"Updating cell ({row}, {col})",
            worksheet.update_cell,
            row,
            col,
            value,
        )
