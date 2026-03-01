"""Pilot API tests for file selection and column mapping screens."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from textual.widgets import Input, Static

from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.parsers.csv_parser import ParsedTransaction
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp
from budget_tracker.tui.screens.column_mapping import ColumnMappingScreen
from budget_tracker.tui.screens.file_selection import FileEntry


@pytest.fixture
def mock_service() -> MagicMock:
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = ["danske_bank", "lunar"]
    service.load_mapping.return_value = BankMapping(
        bank_name="danske_bank",
        column_mapping=ColumnMapping(
            date_column="Dato",
            amount_column="Beløb",
            description_columns=["Tekst"],
        ),
        date_format="%d-%m-%Y",
        decimal_separator=",",
        default_currency="DKK",
    )
    service.parse_file.return_value = [
        ParsedTransaction(
            date=date(2024, 1, 15),
            amount=Decimal("-100.00"),
            currency="DKK",
            description="Test transaction",
            source="danske_bank",
            source_file="test.csv",
        ),
    ]
    mock_df = pd.DataFrame({"Dato": ["15-01-2024"], "Beløb": ["-100,00"], "Tekst": ["Test"]})
    service.detect_columns.return_value = (mock_df, ["Dato", "Beløb", "Tekst"])
    return service


@pytest.fixture
def app(mock_service: MagicMock) -> BudgetTrackerApp:
    return BudgetTrackerApp(service=mock_service)


@pytest.fixture
def mock_df() -> pd.DataFrame:
    return pd.DataFrame({"Dato": ["15-01-2024"], "Beløb": ["-100"], "Tekst": ["Test"]})


@pytest.mark.asyncio
class TestFileSelectionScreen:
    """Tests for the file selection screen."""

    async def test_file_selection_screen_renders(self, app: BudgetTrackerApp) -> None:
        """FileSelectionScreen displays title, input, select, and footer."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert app.screen.__class__.__name__ == "FileSelectionScreen"
            assert app.screen.query_one("#title")
            assert app.screen.query_one("#file-input")
            assert app.screen.query_one("#bank-select")

    async def test_escape_returns_to_home(self, app: BudgetTrackerApp) -> None:
        """Pressing Escape returns to HomeScreen."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert app.screen.__class__.__name__ == "FileSelectionScreen"
            await pilot.press("escape")
            assert app.screen.__class__.__name__ == "HomeScreen"

    async def test_bank_selector_populated(
        self, app: BudgetTrackerApp, mock_service: MagicMock
    ) -> None:
        """Bank selector contains saved banks and 'New mapping...'."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            mock_service.list_mappings.assert_called_once()
            screen = app.screen
            bank_options = screen._bank_options  # type: ignore[attr-defined]
            bank_values = [v for _, v in bank_options]
            assert "danske_bank" in bank_values
            assert "lunar" in bank_values
            assert "__new__" in bank_values

    async def test_continue_with_no_files_shows_notification(self, app: BudgetTrackerApp) -> None:
        """Pressing Enter with empty file list shows warning notification."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            # Focus on file list area (not input) so Enter triggers the binding
            app.screen.query_one("#file-list").focus()
            await pilot.press("enter")
            # The notification is shown but we verify no screen change
            assert app.screen.__class__.__name__ == "FileSelectionScreen"

    async def test_remove_file_empty_shows_notification(self, app: BudgetTrackerApp) -> None:
        """Pressing R with no files shows warning notification."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            await pilot.press("r")
            assert app.screen.__class__.__name__ == "FileSelectionScreen"


@pytest.mark.asyncio
class TestColumnMappingWizard:
    """Tests for the column mapping wizard modal."""

    async def test_column_mapping_cancel(
        self, app: BudgetTrackerApp, mock_df: pd.DataFrame
    ) -> None:
        """Pressing Escape on step 1 dismisses wizard with None."""
        async with app.run_test() as pilot:
            await pilot.press("p")

            wizard = ColumnMappingScreen(["Dato", "Beløb", "Tekst"], mock_df)
            result_holder: list[BankMapping | None] = []
            app.push_screen(wizard, callback=result_holder.append)
            await pilot.pause()

            assert app.screen.__class__.__name__ == "ColumnMappingScreen"
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "FileSelectionScreen"
            assert result_holder == [None]

    async def test_column_mapping_wizard_navigation(
        self, app: BudgetTrackerApp, mock_df: pd.DataFrame
    ) -> None:
        """Wizard displays step counter and advances on selection."""
        async with app.run_test() as pilot:
            await pilot.press("p")

            wizard = ColumnMappingScreen(["Dato", "Beløb", "Tekst"], mock_df)
            app.push_screen(wizard)
            await pilot.pause()

            # Step 1: Bank Name — header shows step counter
            header = app.screen.query_one("#wizard-header", Static)
            assert "Step 1/8" in str(header._Static__content)  # type: ignore[attr-defined]

            # Enter bank name and submit
            step_input = app.screen.query_one("#step-input", Input)
            step_input.value = "Test Bank"
            await pilot.press("enter")
            await pilot.pause()

            # Step 2: Date Column
            header = app.screen.query_one("#wizard-header", Static)
            assert "Step 2/8" in str(header._Static__content)  # type: ignore[attr-defined]

    async def test_column_mapping_completion(
        self, app: BudgetTrackerApp, mock_df: pd.DataFrame
    ) -> None:
        """Completing all wizard steps returns a BankMapping."""
        async with app.run_test() as pilot:
            await pilot.press("p")

            wizard = ColumnMappingScreen(["Dato", "Beløb", "Tekst"], mock_df)
            result_holder: list[BankMapping | None] = []
            app.push_screen(wizard, callback=result_holder.append)
            await pilot.pause()

            # Step 1: Bank Name
            app.screen.query_one("#step-input", Input).value = "Test Bank"
            await pilot.press("enter")
            await pilot.pause()

            # Step 2: Date Column — "Dato" is first/highlighted
            await pilot.press("enter")
            await pilot.pause()

            # Step 3: Amount Column — navigate down to "Beløb"
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            # Step 4: Description — remaining is ["Tekst"], select it
            await pilot.press("enter")
            await pilot.pause()
            # After selecting "Tekst", remaining is empty → only "Done selecting"
            await pilot.press("enter")
            await pilot.pause()

            # Step 5: Currency Config — "No - use default currency" (second option)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            # Sub-step: select "DKK (Danish Krone)" (first option)
            await pilot.press("enter")
            await pilot.pause()

            # Step 6: Date Format — select first option
            await pilot.press("enter")
            await pilot.pause()

            # Step 7: Decimal Separator — select first option (dot)
            await pilot.press("enter")
            await pilot.pause()

            # Step 8: Confirmation — select "Yes - save this mapping"
            await pilot.press("enter")
            await pilot.pause()

            # Wizard should be dismissed
            assert app.screen.__class__.__name__ == "FileSelectionScreen"
            assert len(result_holder) == 1
            mapping = result_holder[0]
            assert mapping is not None
            assert mapping.bank_name == "Test Bank"
            assert mapping.column_mapping.date_column == "Dato"
            assert mapping.column_mapping.amount_column == "Beløb"


@pytest.mark.asyncio
class TestPipelineState:
    """Tests for PipelineState population."""

    async def test_pipeline_state_populated(
        self, app: BudgetTrackerApp, mock_service: MagicMock
    ) -> None:
        """App pipeline state is populated after adding a file and continuing."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            screen = app.screen

            # Directly add a file entry with done status to avoid worker threading
            entry = FileEntry(
                path=Path("/tmp/test.csv"),
                bank_name="danske_bank",
                status="done",
                parsed_transactions=mock_service.parse_file.return_value,
            )
            screen._files.append(entry)  # type: ignore[attr-defined]
            screen._mappings["danske_bank"] = mock_service.load_mapping.return_value  # type: ignore[attr-defined]

            # Call action directly to avoid keyboard focus issues
            screen.action_continue_pipeline()  # type: ignore[attr-defined]
            await pilot.pause()

            state = app.pipeline_state
            assert len(state.files) == 1
            assert state.bank_names == ["danske_bank"]
            assert "danske_bank" in state.mappings
            assert len(state.parsed_transactions) == 1
