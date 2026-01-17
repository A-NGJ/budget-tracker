#!/usr/bin/env python3
"""Test script for Google Sheets authentication flow."""

from datetime import date
from decimal import Decimal

from budget_tracker.clients.google_sheets import GoogleSheetsAuthError, GoogleSheetsClient
from budget_tracker.config.settings import Settings
from budget_tracker.exporters.google_sheets_exporter import GoogleSheetsExporter
from budget_tracker.models.transaction import StandardTransaction


def main() -> None:
    print("=" * 50)
    print("Google Sheets Authentication Test")
    print("=" * 50)

    settings = Settings()

    print(f"\nCredentials directory: {settings.google_credentials_dir}")
    print(f"Credentials file: {settings.google_credentials_file}")
    print(f"Token file: {settings.google_token_file}")

    # Check if credentials.json exists
    if not settings.google_credentials_file.exists():
        print(f"\n❌ credentials.json not found at {settings.google_credentials_file}")
        print("\nTo set up credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Sheets API")
        print("3. Create OAuth 2.0 credentials (Desktop app)")
        print("4. Download and save as ~/.budget-tracker/credentials.json")
        return

    print("\n✓ credentials.json found")

    # Check if already authenticated
    if settings.google_token_file.exists():
        print("✓ token.json found (previously authenticated)")
    else:
        print("○ token.json not found (will need to authenticate)")

    # Try to authenticate
    print("\n" + "-" * 50)
    print("Attempting authentication...")
    print("-" * 50)

    client = GoogleSheetsClient(settings)

    try:
        client.authenticate()
        print("\n✓ Authentication successful!")
    except GoogleSheetsAuthError as e:
        print(f"\n❌ Authentication failed: {e}")
        return

    # Test API access by creating/opening a test spreadsheet
    print("\n" + "-" * 50)
    print("Testing API access...")
    print("-" * 50)

    test_sheet_name = "Budget Tracker Test"
    exporter = GoogleSheetsExporter(settings, test_sheet_name)

    exporter.export(
        [
            StandardTransaction(
                date=date(2101, 6, 1),
                category="Housing",
                amount=Decimal("1.00"),
                source="UnitTest",
                description="Google Sheets API test",
            )
        ]
    )

    # try:
    #     spreadsheet = client.open_or_create_spreadsheet(test_sheet_name)
    #     print(f"\n✓ Successfully accessed spreadsheet: {test_sheet_name}")
    #     print(f"  URL: {spreadsheet.url}")
    #
    #     # Get the first worksheet
    #     worksheet = spreadsheet.sheet1
    #     print(f"  Worksheet: {worksheet.title}")
    #
    #     # Try reading values
    #     values = client.get_all_values(worksheet)
    #     print(f"  Current rows: {len(values)}")
    #
    #     # Write a test value
    #
    #     test_value = f"Auth test: {datetime.now(tz=ZoneInfo('Europe/Copenhagen')).isoformat()}"
    #     client.append_rows(worksheet, [[test_value]])
    #     print(f"  ✓ Wrote test row: {test_value}")
    #
    # except Exception as e:
    #     print(f"\n❌ API test failed: {e}")
    #     return
    #
    # print("\n" + "=" * 50)
    # print("All tests passed! Google Sheets integration is working.")
    # print("=" * 50)


if __name__ == "__main__":
    main()
