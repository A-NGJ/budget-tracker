# Google Sheets Export Implementation Plan

## Overview

Add Google Sheets export capability to the budget tracker with OAuth authentication, automatic sheet-per-year organization, and transaction deduplication via hash-based IDs. This extends the existing CSV-only export system with a proper exporter abstraction layer.

## Current State Analysis

The budget tracker exports standardized transactions exclusively to CSV files via `CSVExporter`. There is no exporter abstraction layer, no Google API integration, and no OAuth implementation.

### Key Discoveries:
- `CSVExporter` class at `src/budget_tracker/exporters/csv_exporter.py:9-51`
- Export invoked at `src/budget_tracker/cli/main.py:157-166`
- No retry logic exists in codebase - HTTP errors are wrapped and re-raised
- Settings use `pydantic_settings.BaseSettings` at `src/budget_tracker/config/settings.py:11-39`
- HTTP client pattern uses `httpx` with explicit timeouts (`exchange_rate_provider.py:47`)

## Desired End State

- `--sheets` flag on `process` command exports to Google Sheets
- OAuth credentials stored in `~/.budget-tracker/credentials.json` with automatic refresh
- One Google Sheet per year (e.g., "Budget 2026")
- Transactions have unique IDs (hash of all fields) to prevent duplicates
- Failed uploads retry with exponential backoff
- CSV export continues to work as before

## What We're NOT Doing

- Web interface or GUI for OAuth (will use device/browser flow)
- Google Drive folder organization
- Sharing/permissions management
- Real-time sync or webhooks
- Multiple Google accounts support

## Implementation Approach

Introduce an `Exporter` protocol that both `CSVExporter` and new `GoogleSheetsExporter` implement. Add transaction ID generation to the model. Build a Google Sheets client with OAuth and retry logic. Integrate via a new CLI flag.

---

## Phase 1: Exporter Protocol

### Overview
Create a base `Exporter` protocol that defines the interface for all exporters. Refactor `CSVExporter` to implement it.

### Changes Required:

#### 1. Create Exporter Protocol
**File**: `src/budget_tracker/exporters/base.py` (new)
**Changes**: Define the protocol

```python
from typing import Protocol

from budget_tracker.models.transaction import StandardTransaction


class Exporter(Protocol):
    """Protocol for transaction exporters."""

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to the target destination.

        Args:
            transactions: List of standardized transactions to export

        Returns:
            String describing where the data was exported (file path or URL)
        """
        ...
```

#### 2. Update CSVExporter to match protocol
**File**: `src/budget_tracker/exporters/csv_exporter.py`
**Changes**: Adjust signature to return `str` instead of `Path`, make `output_file` a constructor parameter

```python
from pathlib import Path

import pandas as pd

from budget_tracker.config.settings import Settings
from budget_tracker.models.transaction import StandardTransaction


class CSVExporter:
    """Export standardized transactions to CSV"""

    def __init__(self, settings: Settings, output_file: Path | None = None) -> None:
        self.output_dir = settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = output_file or (self.output_dir / settings.default_output_filename)

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to standardized CSV.

        Args:
            transactions: List of standardized transactions

        Returns:
            Path to created file as string
        """
        data = []
        for t in transactions:
            row = {
                "Date": t.date.strftime("%Y-%m-%d"),
                "Description": t.description,
                "Category": t.category,
                "Subcategory": t.subcategory,
                "Amount (DKK)": float(t.amount),
                "Source": t.source,
            }
            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("Date")
        df = df[["Date", "Description", "Category", "Subcategory", "Amount (DKK)", "Source"]]
        df.to_csv(self.output_file, index=False)

        return str(self.output_file)
```

#### 3. Update exporters __init__.py
**File**: `src/budget_tracker/exporters/__init__.py`
**Changes**: Export the protocol and CSVExporter

```python
from budget_tracker.exporters.base import Exporter
from budget_tracker.exporters.csv_exporter import CSVExporter

__all__ = ["Exporter", "CSVExporter"]
```

#### 4. Update CLI to use new signature
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Update lines 157-163 to pass output_file to constructor

```python
# Step 5: Export
output_file = output or (settings.output_dir / settings.default_output_filename)
exporter = CSVExporter(_settings, output_file=output_file)
result_path = exporter.export(standardized)

console.print("\n[bold green]✓ Success![/bold green]")
console.print(f"Output written to: {result_path}")
```

#### 5. Update existing exporter tests
**File**: `tests/unit/test_exporter.py`
**Changes**: Update tests for new signature

```python
class TestCSVExporter:
    def test_export_creates_csv_file(self, settings: Settings, tmp_path: Path) -> None:
        """Test that export creates a CSV file"""
        output_file = tmp_path / "output.csv"
        exporter = CSVExporter(settings, output_file=output_file)

        transactions = [create_test_transaction()]
        result = exporter.export(transactions)

        assert result == str(output_file)
        assert output_file.exists()

    def test_exporter_implements_protocol(self, settings: Settings) -> None:
        """Test that CSVExporter implements Exporter protocol"""
        from budget_tracker.exporters.base import Exporter

        exporter = CSVExporter(settings)
        assert isinstance(exporter, Exporter)
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_exporter.py`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] `budget-tracker process` still works and creates CSV output

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Transaction ID Generation

### Overview
Add a `transaction_id` property to `StandardTransaction` that generates a unique hash from all fields. This ID will be used to detect and skip duplicate transactions when appending to Google Sheets.

### Changes Required:

#### 1. Add transaction_id property
**File**: `src/budget_tracker/models/transaction.py`
**Changes**: Add computed property using SHA256 hash

```python
import hashlib
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

# ... existing code ...

class StandardTransaction(BaseModel):
    """Standardized transaction after categorization"""

    date: date
    category: str
    subcategory: str | None = None
    amount: Decimal
    source: str
    description: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # ... existing validators ...

    @property
    def transaction_id(self) -> str:
        """
        Generate unique transaction ID from all fields.

        Uses SHA256 hash of concatenated fields to create a stable,
        unique identifier for deduplication purposes.
        """
        # Normalize values for consistent hashing
        parts = [
            self.date.isoformat(),
            self.category,
            self.subcategory or "",
            str(self.amount),
            self.source,
            self.description or "",
        ]
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

#### 2. Update CSVExporter to include transaction ID
**File**: `src/budget_tracker/exporters/csv_exporter.py`
**Changes**: Add Transaction ID column

```python
def export(self, transactions: list[StandardTransaction]) -> str:
    data = []
    for t in transactions:
        row = {
            "Transaction ID": t.transaction_id,
            "Date": t.date.strftime("%Y-%m-%d"),
            "Description": t.description,
            "Category": t.category,
            "Subcategory": t.subcategory,
            "Amount (DKK)": float(t.amount),
            "Source": t.source,
        }
        data.append(row)

    df = pd.DataFrame(data)
    df = df.sort_values("Date")
    df = df[["Transaction ID", "Date", "Description", "Category", "Subcategory", "Amount (DKK)", "Source"]]
    df.to_csv(self.output_file, index=False)

    return str(self.output_file)
```

#### 3. Add transaction ID tests
**File**: `tests/unit/test_transaction.py` (new or extend existing)
**Changes**: Test transaction_id property

```python
from datetime import date
from decimal import Decimal

import pytest

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
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_transaction.py`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] Run `budget-tracker process` and verify CSV now has Transaction ID column

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 3: Google Sheets Client

### Overview
Create a Google Sheets client with OAuth2 authentication (interactive browser flow), credential storage in `~/.budget-tracker/`, and retry logic with exponential backoff.

### Changes Required:

#### 1. Add Google dependencies
**File**: `pyproject.toml`
**Changes**: Add google-auth and gspread packages

```toml
dependencies = [
    "typer[all]>=0.12.0",
    "pandas>=2.2.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.3.0",
    "ollama>=0.3.0",
    "pyyaml>=6.0.1",
    "rich>=13.7.0",
    "httpx>=0.27.0",
    "gspread>=6.0.0",
    "google-auth-oauthlib>=1.2.0",
]
```

#### 2. Add credential settings
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Add Google Sheets settings

```python
class Settings(BaseSettings):
    """Application settings."""

    # ... existing settings ...

    # Google Sheets settings
    google_credentials_dir: Path = Path.home() / ".budget-tracker"
    google_credentials_file: Path = Path.home() / ".budget-tracker" / "credentials.json"
    google_token_file: Path = Path.home() / ".budget-tracker" / "token.json"
    google_sheets_retry_attempts: int = 3
    google_sheets_retry_base_delay: float = 1.0  # seconds
```

#### 3. Create Google Sheets client
**File**: `src/budget_tracker/clients/google_sheets.py` (new)
**Changes**: OAuth client with retry logic

```python
"""Google Sheets client with OAuth authentication and retry logic."""

import json
import time
from pathlib import Path
from typing import Any

import gspread
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from rich.console import Console

from budget_tracker.config.settings import Settings

console = Console()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsAuthError(Exception):
    """Raised when Google Sheets authentication fails."""
    pass


class GoogleSheetsClient:
    """
    Google Sheets client with OAuth2 authentication and retry logic.

    Credentials are stored in ~/.budget-tracker/ and automatically refreshed.
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
        """Refresh expired credentials."""
        try:
            credentials.refresh(Request())
            self._save_credentials(credentials)
            return credentials
        except RefreshError as e:
            # Token is invalid, need to re-authenticate
            self.token_file.unlink(missing_ok=True)
            raise GoogleSheetsAuthError(
                "Credentials expired and refresh failed. Please re-authenticate."
            ) from e

    def _authenticate_interactive(self) -> Credentials:
        """Run interactive OAuth flow in browser."""
        if not self.credentials_file.exists():
            raise GoogleSheetsAuthError(
                f"Google OAuth credentials not found at {self.credentials_file}. "
                "Please download credentials.json from Google Cloud Console."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_file), SCOPES
        )
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

    def _with_retry(self, operation: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            operation: Description of the operation for error messages
            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result of the function call

        Raises:
            Last exception if all retries fail
        """
        last_exception: Exception | None = None

        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    console.print(
                        f"[yellow]⚠[/yellow] {operation} failed (attempt {attempt + 1}/"
                        f"{self.retry_attempts}), retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

        raise last_exception  # type: ignore[misc]

    @property
    def client(self) -> gspread.Client:
        """Get authenticated gspread client."""
        if self._client is None:
            raise GoogleSheetsAuthError("Not authenticated. Call authenticate() first.")
        return self._client

    def open_or_create_spreadsheet(self, title: str) -> gspread.Spreadsheet:
        """
        Open existing spreadsheet or create new one.

        Args:
            title: Spreadsheet title to find or create

        Returns:
            gspread Spreadsheet object
        """
        def _open_or_create() -> gspread.Spreadsheet:
            try:
                return self.client.open(title)
            except gspread.SpreadsheetNotFound:
                return self.client.create(title)

        return self._with_retry(f"Opening spreadsheet '{title}'", _open_or_create)

    def get_all_values(self, worksheet: gspread.Worksheet) -> list[list[str]]:
        """Get all values from worksheet with retry."""
        return self._with_retry(
            "Fetching worksheet data",
            worksheet.get_all_values
        )

    def append_rows(
        self,
        worksheet: gspread.Worksheet,
        rows: list[list[Any]],
        value_input_option: str = "USER_ENTERED"
    ) -> None:
        """Append rows to worksheet with retry."""
        self._with_retry(
            f"Appending {len(rows)} rows",
            worksheet.append_rows,
            rows,
            value_input_option=value_input_option
        )

    def update_cell(self, worksheet: gspread.Worksheet, row: int, col: int, value: Any) -> None:
        """Update single cell with retry."""
        self._with_retry(
            f"Updating cell ({row}, {col})",
            worksheet.update_cell,
            row, col, value
        )
```

#### 4. Create clients package
**File**: `src/budget_tracker/clients/__init__.py` (new)
**Changes**: Export client

```python
from budget_tracker.clients.google_sheets import GoogleSheetsClient, GoogleSheetsAuthError

__all__ = ["GoogleSheetsClient", "GoogleSheetsAuthError"]
```

#### 5. Add Google Sheets client tests
**File**: `tests/unit/test_google_sheets_client.py` (new)
**Changes**: Test retry logic and credential handling

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import gspread
import pytest

from budget_tracker.clients.google_sheets import (
    GoogleSheetsClient,
    GoogleSheetsAuthError,
)
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
        """Test that retry succeeds after transient failure."""
        mock_func = MagicMock(side_effect=[
            gspread.exceptions.APIError({"code": 500}),
            "success"
        ])

        result = client._with_retry("test operation", mock_func)

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_exhausts_attempts(self, client: GoogleSheetsClient) -> None:
        """Test that retry raises after all attempts fail."""
        error = gspread.exceptions.APIError({"code": 500})
        mock_func = MagicMock(side_effect=error)

        with pytest.raises(gspread.exceptions.APIError):
            client._with_retry("test operation", mock_func)

        assert mock_func.call_count == 3

    def test_retry_uses_exponential_backoff(self, client: GoogleSheetsClient) -> None:
        """Test that delays increase exponentially."""
        mock_func = MagicMock(side_effect=gspread.exceptions.APIError({"code": 500}))

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(gspread.exceptions.APIError):
                client._with_retry("test", mock_func)

            # Should have slept twice (not after final attempt)
            assert mock_sleep.call_count == 2
            # First delay: base * 2^0 = 0.01
            # Second delay: base * 2^1 = 0.02
            mock_sleep.assert_any_call(0.01)
            mock_sleep.assert_any_call(0.02)


class TestAuthentication:
    def test_authenticate_raises_without_credentials_file(
        self, client: GoogleSheetsClient
    ) -> None:
        """Test error when credentials.json missing."""
        with pytest.raises(GoogleSheetsAuthError, match="credentials not found"):
            client._authenticate_interactive()

    def test_client_property_raises_before_auth(self, client: GoogleSheetsClient) -> None:
        """Test that client property raises before authenticate()."""
        with pytest.raises(GoogleSheetsAuthError, match="Not authenticated"):
            _ = client.client

    def test_load_credentials_returns_none_if_no_token(
        self, client: GoogleSheetsClient
    ) -> None:
        """Test that missing token file returns None."""
        assert client._load_credentials() is None


class TestSpreadsheetOperations:
    def test_open_or_create_opens_existing(self, client: GoogleSheetsClient) -> None:
        """Test opening existing spreadsheet."""
        mock_spreadsheet = MagicMock()
        mock_gspread_client = MagicMock()
        mock_gspread_client.open.return_value = mock_spreadsheet
        client._client = mock_gspread_client

        result = client.open_or_create_spreadsheet("Budget 2026")

        mock_gspread_client.open.assert_called_once_with("Budget 2026")
        assert result == mock_spreadsheet

    def test_open_or_create_creates_when_not_found(
        self, client: GoogleSheetsClient
    ) -> None:
        """Test creating spreadsheet when not found."""
        mock_spreadsheet = MagicMock()
        mock_gspread_client = MagicMock()
        mock_gspread_client.open.side_effect = gspread.SpreadsheetNotFound
        mock_gspread_client.create.return_value = mock_spreadsheet
        client._client = mock_gspread_client

        result = client.open_or_create_spreadsheet("Budget 2026")

        mock_gspread_client.create.assert_called_once_with("Budget 2026")
        assert result == mock_spreadsheet
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_google_sheets_client.py`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] Place a test `credentials.json` in `~/.budget-tracker/`
- [x] Write a small script to test authentication flow opens browser

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 4: GoogleSheetsExporter

### Overview
Create the `GoogleSheetsExporter` class that implements the `Exporter` protocol. Handles sheet-per-year organization and transaction deduplication.

### Changes Required:

#### 1. Create GoogleSheetsExporter
**File**: `src/budget_tracker/exporters/google_sheets_exporter.py` (new)
**Changes**: Full exporter implementation

```python
"""Export transactions to Google Sheets."""

from typing import Any

from rich.console import Console

from budget_tracker.clients.google_sheets import GoogleSheetsClient
from budget_tracker.config.settings import Settings
from budget_tracker.models.transaction import StandardTransaction

console = Console()

SHEET_COLUMNS = [
    "Transaction ID",
    "Date",
    "Description",
    "Category",
    "Subcategory",
    "Amount (DKK)",
    "Source",
]


class GoogleSheetsExporter:
    """
    Export transactions to Google Sheets.

    Organizes transactions into one sheet per year. Detects and skips
    duplicate transactions using transaction IDs.
    """

    def __init__(self, settings: Settings, sheet_name_prefix: str = "Budget") -> None:
        """
        Initialize the exporter.

        Args:
            settings: Application settings
            sheet_name_prefix: Prefix for spreadsheet names (e.g., "Budget" -> "Budget 2026")
        """
        self.settings = settings
        self.sheet_name_prefix = sheet_name_prefix
        self.client = GoogleSheetsClient(settings)

    def _get_sheet_name(self, year: int) -> str:
        """Generate spreadsheet name for a year."""
        return f"{self.sheet_name_prefix} {year}"

    def _transaction_to_row(self, t: StandardTransaction) -> list[Any]:
        """Convert transaction to row values."""
        return [
            t.transaction_id,
            t.date.strftime("%Y-%m-%d"),
            t.description or "",
            t.category,
            t.subcategory or "",
            float(t.amount),
            t.source,
        ]

    def _get_existing_transaction_ids(self, worksheet: Any) -> set[str]:
        """Get set of transaction IDs already in worksheet."""
        values = self.client.get_all_values(worksheet)
        if len(values) <= 1:  # Empty or only header
            return set()

        # Transaction ID is first column
        return {row[0] for row in values[1:] if row}

    def _ensure_header(self, worksheet: Any) -> None:
        """Ensure worksheet has header row."""
        values = self.client.get_all_values(worksheet)
        if not values:
            self.client.append_rows(worksheet, [SHEET_COLUMNS])

    def _group_by_year(
        self, transactions: list[StandardTransaction]
    ) -> dict[int, list[StandardTransaction]]:
        """Group transactions by year."""
        by_year: dict[int, list[StandardTransaction]] = {}
        for t in transactions:
            year = t.date.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(t)
        return by_year

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to Google Sheets.

        Creates one spreadsheet per year. Skips transactions that already
        exist (based on transaction ID).

        Args:
            transactions: List of standardized transactions

        Returns:
            Summary string of export results
        """
        if not transactions:
            return "No transactions to export"

        # Authenticate
        self.client.authenticate()

        # Group by year
        by_year = self._group_by_year(transactions)

        results: list[str] = []
        total_added = 0
        total_skipped = 0

        for year, year_transactions in sorted(by_year.items()):
            sheet_name = self._get_sheet_name(year)
            console.print(f"\n[cyan]Processing {sheet_name}...[/cyan]")

            # Open or create spreadsheet
            spreadsheet = self.client.open_or_create_spreadsheet(sheet_name)
            worksheet = spreadsheet.sheet1

            # Ensure header exists
            self._ensure_header(worksheet)

            # Get existing transaction IDs
            existing_ids = self._get_existing_transaction_ids(worksheet)

            # Filter out duplicates
            new_transactions = [
                t for t in year_transactions
                if t.transaction_id not in existing_ids
            ]

            skipped = len(year_transactions) - len(new_transactions)
            total_skipped += skipped

            if skipped > 0:
                console.print(
                    f"[yellow]⚠[/yellow] Skipping {skipped} duplicate transaction(s)"
                )

            if new_transactions:
                # Convert to rows and append
                rows = [self._transaction_to_row(t) for t in new_transactions]
                self.client.append_rows(worksheet, rows)
                total_added += len(new_transactions)
                console.print(
                    f"[green]✓[/green] Added {len(new_transactions)} transaction(s) "
                    f"to {sheet_name}"
                )

            results.append(
                f"{sheet_name}: {len(new_transactions)} added, {skipped} skipped"
            )

        summary = f"Google Sheets export complete: {total_added} added, {total_skipped} skipped"
        return summary
```

#### 2. Update exporters __init__.py
**File**: `src/budget_tracker/exporters/__init__.py`
**Changes**: Export GoogleSheetsExporter

```python
from budget_tracker.exporters.base import Exporter
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.exporters.google_sheets_exporter import GoogleSheetsExporter

__all__ = ["Exporter", "CSVExporter", "GoogleSheetsExporter"]
```

#### 3. Add GoogleSheetsExporter tests
**File**: `tests/unit/test_google_sheets_exporter.py` (new)
**Changes**: Test exporter logic

```python
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_tracker.config.settings import Settings
from budget_tracker.exporters.google_sheets_exporter import (
    GoogleSheetsExporter,
    SHEET_COLUMNS,
)
from budget_tracker.models.transaction import StandardTransaction


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        google_credentials_dir=tmp_path,
        google_credentials_file=tmp_path / "credentials.json",
        google_token_file=tmp_path / "token.json",
    )


@pytest.fixture
def exporter(settings: Settings) -> GoogleSheetsExporter:
    return GoogleSheetsExporter(settings)


@pytest.fixture
def sample_transaction() -> StandardTransaction:
    return StandardTransaction(
        date=date(2026, 1, 15),
        category="Food & Drinks",
        subcategory="Groceries",
        amount=Decimal("150.00"),
        source="danske_bank",
        description="Supermarket purchase",
    )


class TestGroupByYear:
    def test_groups_transactions_by_year(self, exporter: GoogleSheetsExporter) -> None:
        """Test that transactions are grouped by year."""
        t2025 = StandardTransaction(
            date=date(2025, 12, 31),
            category="Food & Drinks",
            amount=Decimal("100"),
            source="bank",
        )
        t2026 = StandardTransaction(
            date=date(2026, 1, 1),
            category="Food & Drinks",
            amount=Decimal("200"),
            source="bank",
        )

        result = exporter._group_by_year([t2025, t2026])

        assert 2025 in result
        assert 2026 in result
        assert len(result[2025]) == 1
        assert len(result[2026]) == 1


class TestTransactionToRow:
    def test_converts_transaction_to_row(
        self, exporter: GoogleSheetsExporter, sample_transaction: StandardTransaction
    ) -> None:
        """Test transaction to row conversion."""
        row = exporter._transaction_to_row(sample_transaction)

        assert row[0] == sample_transaction.transaction_id
        assert row[1] == "2026-01-15"
        assert row[2] == "Supermarket purchase"
        assert row[3] == "Food & Drinks"
        assert row[4] == "Groceries"
        assert row[5] == 150.0
        assert row[6] == "danske_bank"

    def test_handles_none_values(self, exporter: GoogleSheetsExporter) -> None:
        """Test that None values become empty strings."""
        t = StandardTransaction(
            date=date(2026, 1, 1),
            category="Other",
            subcategory=None,
            amount=Decimal("100"),
            source="bank",
            description=None,
        )

        row = exporter._transaction_to_row(t)

        assert row[2] == ""  # description
        assert row[4] == ""  # subcategory


class TestDuplicateDetection:
    def test_filters_duplicate_transactions(
        self, exporter: GoogleSheetsExporter, sample_transaction: StandardTransaction
    ) -> None:
        """Test that existing transactions are filtered out."""
        existing_ids = {sample_transaction.transaction_id}

        # Should be filtered
        assert sample_transaction.transaction_id in existing_ids


class TestSheetName:
    def test_generates_sheet_name(self, exporter: GoogleSheetsExporter) -> None:
        """Test sheet name generation."""
        assert exporter._get_sheet_name(2026) == "Budget 2026"

    def test_custom_prefix(self, settings: Settings) -> None:
        """Test custom sheet name prefix."""
        exporter = GoogleSheetsExporter(settings, sheet_name_prefix="Expenses")
        assert exporter._get_sheet_name(2026) == "Expenses 2026"


class TestExport:
    def test_export_empty_list_returns_message(
        self, exporter: GoogleSheetsExporter
    ) -> None:
        """Test exporting empty list."""
        result = exporter.export([])
        assert result == "No transactions to export"

    @patch.object(GoogleSheetsExporter, "client", new_callable=MagicMock)
    def test_export_creates_spreadsheet_per_year(
        self,
        mock_client_property: MagicMock,
        exporter: GoogleSheetsExporter,
    ) -> None:
        """Test that separate spreadsheets are created per year."""
        # Setup mocks
        mock_client = MagicMock()
        exporter.client = mock_client
        mock_client.authenticate = MagicMock()

        mock_worksheet = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = mock_worksheet
        mock_client.open_or_create_spreadsheet.return_value = mock_spreadsheet
        mock_client.get_all_values.return_value = [SHEET_COLUMNS]  # Just header

        transactions = [
            StandardTransaction(
                date=date(2025, 6, 1),
                category="Food & Drinks",
                amount=Decimal("100"),
                source="bank",
            ),
            StandardTransaction(
                date=date(2026, 1, 1),
                category="Food & Drinks",
                amount=Decimal("200"),
                source="bank",
            ),
        ]

        exporter.export(transactions)

        # Should open/create two spreadsheets
        assert mock_client.open_or_create_spreadsheet.call_count == 2
        mock_client.open_or_create_spreadsheet.assert_any_call("Budget 2025")
        mock_client.open_or_create_spreadsheet.assert_any_call("Budget 2026")
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_google_sheets_exporter.py`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] With valid credentials, manually test exporting a few transactions to Google Sheets

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 5: CLI Integration

### Overview
Add `--sheets` flag to the `process` command that triggers Google Sheets export in addition to (or instead of) CSV export.

### Changes Required:

#### 1. Add --sheets flag to CLI
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Add flag and conditional export logic

```python
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.exporters.google_sheets_exporter import GoogleSheetsExporter

# ... in process command definition ...

@app.command()
def process(
    ctx: typer.Context,
    files: Annotated[list[Path], typer.Argument(help="CSV files to process")],
    banks: Annotated[
        list[str],
        typer.Option(
            "--banks", "-b", help="Bank name(s) for mapping lookup. Must match number of files."
        ),
    ],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output CSV file path")
    ] = None,
    sheets: Annotated[
        bool, typer.Option("--sheets", help="Export to Google Sheets")
    ] = False,
) -> None:
    """
    Process bank statement CSV files and generate standardized output.

    Examples:
        budget-tracker process bank1.csv -b danske_bank
        budget-tracker process bank1.csv -b danske_bank --sheets
        budget-tracker process bank1.csv bank2.csv -b danske_bank -b nordea --output results.csv
    """
    # ... existing processing code ...

    # Step 5: Export
    output_file = output or (settings.output_dir / settings.default_output_filename)

    # Always export to CSV
    csv_exporter = CSVExporter(_settings, output_file=output_file)
    result_path = csv_exporter.export(standardized)
    console.print("\n[bold green]✓ Success![/bold green]")
    console.print(f"CSV output written to: {result_path}")

    # Optionally export to Google Sheets
    if sheets:
        console.print("\n[cyan]Exporting to Google Sheets...[/cyan]")
        try:
            sheets_exporter = GoogleSheetsExporter(_settings)
            sheets_result = sheets_exporter.export(standardized)
            console.print(f"[green]✓[/green] {sheets_result}")
        except Exception as e:
            console.print(f"[red]✗[/red] Google Sheets export failed: {e}")
            console.print("[yellow]CSV export completed successfully.[/yellow]")

    # Print summary
    print_summary(standardized)
```

#### 2. Add CLI integration tests
**File**: `tests/integration/test_cli_sheets.py` (new)
**Changes**: Test CLI with --sheets flag

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from budget_tracker.cli.main import create_app
from budget_tracker.config.settings import Settings


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        banks_dir=tmp_path / "banks",
        google_credentials_dir=tmp_path / ".budget-tracker",
        google_credentials_file=tmp_path / ".budget-tracker" / "credentials.json",
        google_token_file=tmp_path / ".budget-tracker" / "token.json",
    )


class TestSheetsFlag:
    def test_sheets_flag_exists(self, runner: CliRunner, settings: Settings) -> None:
        """Test that --sheets flag is recognized."""
        app = create_app(settings)
        result = runner.invoke(app, ["process", "--help"])

        assert "--sheets" in result.output
        assert "Export to Google Sheets" in result.output

    @patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
    @patch("budget_tracker.cli.main.GoogleSheetsExporter")
    @patch("budget_tracker.cli.main.CSVExporter")
    @patch("budget_tracker.cli.main.LLMCategorizer")
    @patch("budget_tracker.cli.main.CSVParser")
    def test_sheets_flag_triggers_sheets_export(
        self,
        mock_parser: MagicMock,
        mock_categorizer: MagicMock,
        mock_csv_exporter: MagicMock,
        mock_sheets_exporter: MagicMock,
        mock_ollama: MagicMock,
        runner: CliRunner,
        settings: Settings,
        tmp_path: Path,
    ) -> None:
        """Test that --sheets flag triggers Google Sheets export."""
        # Setup
        settings.banks_dir.mkdir(parents=True, exist_ok=True)

        # Create test bank mapping
        bank_file = settings.banks_dir / "test_bank.yaml"
        bank_file.write_text("""
bank_name: test_bank
column_mapping:
  date_column: Date
  amount_column: Amount
  description_columns: [Description]
date_format: "%Y-%m-%d"
decimal_separator: "."
default_currency: DKK
""")

        # Create test CSV
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Date,Amount,Description\n2026-01-01,100,Test\n")

        # Mock parser to return transactions
        from budget_tracker.parsers.csv_parser import ParsedTransaction
        from datetime import date
        from decimal import Decimal

        mock_parser_instance = MagicMock()
        mock_parser_instance.load_with_mapping.return_value = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Test",
                source="test_bank",
                source_file="test.csv",
            )
        ]
        mock_parser.return_value = mock_parser_instance

        # Mock categorizer
        from budget_tracker.categorizer.llm_categorizer import CategoryResult
        mock_cat_instance = MagicMock()
        mock_cat_instance.categorize.return_value = CategoryResult(
            category="Other",
            subcategory="Uncategorized",
            confidence=1.0,
            needs_confirmation=False,
        )
        mock_categorizer.return_value = mock_cat_instance

        # Mock exporters
        mock_csv_instance = MagicMock()
        mock_csv_instance.export.return_value = str(tmp_path / "output.csv")
        mock_csv_exporter.return_value = mock_csv_instance

        mock_sheets_instance = MagicMock()
        mock_sheets_instance.export.return_value = "Exported 1 transaction"
        mock_sheets_exporter.return_value = mock_sheets_instance

        app = create_app(settings)

        with patch("budget_tracker.cli.main.CurrencyConverter"):
            with patch("budget_tracker.cli.main.confirm_uncertain_categories", side_effect=lambda s, t: t):
                result = runner.invoke(
                    app,
                    ["process", str(test_csv), "-b", "test_bank", "--sheets"]
                )

        # Verify Google Sheets exporter was called
        mock_sheets_exporter.assert_called_once()
        mock_sheets_instance.export.assert_called_once()

    @patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
    @patch("budget_tracker.cli.main.CSVExporter")
    @patch("budget_tracker.cli.main.LLMCategorizer")
    @patch("budget_tracker.cli.main.CSVParser")
    def test_without_sheets_flag_no_sheets_export(
        self,
        mock_parser: MagicMock,
        mock_categorizer: MagicMock,
        mock_csv_exporter: MagicMock,
        mock_ollama: MagicMock,
        runner: CliRunner,
        settings: Settings,
        tmp_path: Path,
    ) -> None:
        """Test that without --sheets flag, only CSV export happens."""
        # This test verifies GoogleSheetsExporter is NOT imported/called
        # when --sheets is not provided
        pass  # Implementation similar to above but without --sheets
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/integration/test_cli_sheets.py`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] Run `budget-tracker process --help` and verify --sheets flag appears
- [ ] Run full flow: `budget-tracker process bank_export.csv -b danske_bank --sheets`
- [ ] Verify CSV file created AND Google Sheet created/updated

**Note**: Pause for manual confirmation before proceeding.

---

## Testing Strategy

### Unit Tests:
- `test_exporter.py` - CSVExporter protocol compliance, output format
- `test_transaction.py` - Transaction ID generation, determinism, edge cases
- `test_google_sheets_client.py` - Retry logic, credential handling, mock API calls
- `test_google_sheets_exporter.py` - Year grouping, deduplication, row conversion

### Integration Tests:
- `test_cli_sheets.py` - End-to-end CLI with --sheets flag

### Manual Testing:
1. Download OAuth credentials from Google Cloud Console
2. Place `credentials.json` in `~/.budget-tracker/`
3. Run `budget-tracker process sample.csv -b danske_bank --sheets`
4. Verify browser opens for OAuth consent
5. Verify spreadsheet created in Google Drive
6. Run same command again - verify duplicates are skipped
7. Test with transactions spanning multiple years

## References

- Research document: `.claude/thoughts/shared/research/2026-01-02-google-sheets-integration-research.md`
- Current exporter: `src/budget_tracker/exporters/csv_exporter.py:9-51`
- CLI process command: `src/budget_tracker/cli/main.py:41-166`
- HTTP client pattern: `src/budget_tracker/currency/exchange_rate_provider.py:47-72`
- gspread documentation: https://docs.gspread.org/
- Google OAuth2 documentation: https://developers.google.com/identity/protocols/oauth2
