"""Pilot API tests for secondary screens: Blacklist, Mappings, Cache clear."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, OptionList, Select, Static

from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.app import BudgetTrackerApp

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_service(
    *, banks: list[str] | None = None, keywords: list[str] | None = None
) -> MagicMock:
    """Create a mock BudgetService with common defaults."""
    service = MagicMock(spec=BudgetService)
    service.list_mappings.return_value = banks if banks is not None else ["danske_bank", "lunar"]
    service.load_bank_blacklist.return_value = (
        keywords if keywords is not None else ["OVERFOERSEL", "MOBILEPAY"]
    )
    return service


async def _push_blacklist(app: BudgetTrackerApp, pilot: object) -> None:
    """Navigate from home to blacklist screen."""
    app.push_screen("blacklist")
    await pilot.pause()  # type: ignore[attr-defined]


# ── BlacklistScreen Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestBlacklistScreen:
    """Tests for the blacklist management screen."""

    async def test_blacklist_screen_renders(self) -> None:
        """BlacklistScreen shows title and bank selector."""
        app = BudgetTrackerApp(service=_make_service())
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)
            assert app.screen.__class__.__name__ == "BlacklistScreen"
            assert app.screen.query_one("#title", Static)

    async def test_bank_select_loads_keywords(self) -> None:
        """Selecting a bank populates the keyword list."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            service.load_bank_blacklist.assert_called_with("danske_bank")
            keyword_list = app.screen.query_one("#keyword-list", OptionList)
            assert keyword_list.option_count == 2

    async def test_add_keyword(self) -> None:
        """Adding a keyword calls the service and refreshes the list."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            keyword_input = app.screen.query_one("#keyword-input", Input)
            keyword_input.value = "NEW_KEYWORD"
            await pilot.click("#add-btn")
            await pilot.pause()

            service.add_blacklist_keyword.assert_called_once_with("danske_bank", "NEW_KEYWORD")

    async def test_add_empty_keyword_ignored(self) -> None:
        """Empty input does not call the service."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            # Input is empty by default
            await pilot.click("#add-btn")
            await pilot.pause()

            service.add_blacklist_keyword.assert_not_called()

    async def test_add_duplicate_keyword_ignored(self) -> None:
        """Duplicate keyword does not call the service."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            keyword_input = app.screen.query_one("#keyword-input", Input)
            keyword_input.value = "OVERFOERSEL"  # already in the list
            await pilot.click("#add-btn")
            await pilot.pause()

            service.add_blacklist_keyword.assert_not_called()

    async def test_remove_keyword(self) -> None:
        """Pressing delete removes the highlighted keyword."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            # highlighted is set to 0 by _refresh_keyword_list
            await pilot.press("delete")
            await pilot.pause()

            service.remove_blacklist_keyword.assert_called_once_with("danske_bank", "OVERFOERSEL")

    async def test_escape_returns_home(self) -> None:
        """Escape pops back to the home screen."""
        app = BudgetTrackerApp(service=_make_service())
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)
            assert app.screen.__class__.__name__ == "BlacklistScreen"

            await pilot.press("escape")
            assert app.screen.__class__.__name__ == "HomeScreen"

    async def test_no_banks_shows_message(self) -> None:
        """Empty bank list shows a 'no banks' message."""
        service = _make_service(banks=[])
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            no_banks_msg = app.screen.query_one("#no-banks-msg", Static)
            assert no_banks_msg.display is True
            bank_row = app.screen.query_one("#bank-row")
            assert bank_row.display is False

    async def test_keyword_input_submit_adds(self) -> None:
        """Pressing Enter in the keyword input adds the keyword."""
        service = _make_service()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_blacklist(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            keyword_input = app.screen.query_one("#keyword-input", Input)
            keyword_input.value = "ENTER_KEYWORD"
            keyword_input.focus()
            await pilot.press("enter")
            await pilot.pause()

            service.add_blacklist_keyword.assert_called_once_with("danske_bank", "ENTER_KEYWORD")


async def _push_mappings(app: BudgetTrackerApp, pilot: object) -> None:
    """Navigate from home to mappings screen."""
    app.push_screen("mappings")
    await pilot.pause()  # type: ignore[attr-defined]


# ── MappingsScreen Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestMappingsScreen:
    """Tests for the read-only mappings viewer."""

    async def test_mappings_screen_renders(self) -> None:
        """MappingsScreen shows title and bank selector."""
        app = BudgetTrackerApp(service=_make_service())
        async with app.run_test() as pilot:
            await _push_mappings(app, pilot)
            assert app.screen.__class__.__name__ == "MappingsScreen"
            assert app.screen.query_one("#title", Static)

    async def test_bank_select_shows_mapping_details(self) -> None:
        """Selecting a bank displays the mapping details."""
        service = _make_service()
        service.load_mapping.return_value = _make_bank_mapping()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_mappings(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            service.load_mapping.assert_called_with("danske_bank")
            details = app.screen.query_one("#mapping-details", Static)
            rendered = str(details.render())
            assert "danske_bank" in rendered

    async def test_mapping_details_content(self) -> None:
        """All mapping fields are shown in the details view."""
        service = _make_service()
        service.load_mapping.return_value = _make_bank_mapping()
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_mappings(app, pilot)

            select = app.screen.query_one("#bank-select", Select)
            select.value = "danske_bank"
            await pilot.pause()
            await pilot.pause()

            details = app.screen.query_one("#mapping-details", Static)
            rendered = str(details.render())
            for expected in ["Dato", "Beløb", "Tekst", "%d-%m-%Y", "DKK"]:
                assert expected in rendered, f"Expected '{expected}' in mapping details"

    async def test_no_banks_shows_message(self) -> None:
        """Empty bank list shows a 'no banks' message."""
        service = _make_service(banks=[])
        app = BudgetTrackerApp(service=service)
        async with app.run_test() as pilot:
            await _push_mappings(app, pilot)

            no_banks_msg = app.screen.query_one("#no-banks-msg", Static)
            assert no_banks_msg.display is True
            bank_row = app.screen.query_one("#bank-row")
            assert bank_row.display is False

    async def test_escape_returns_home(self) -> None:
        """Escape pops back to the home screen."""
        app = BudgetTrackerApp(service=_make_service())
        async with app.run_test() as pilot:
            await _push_mappings(app, pilot)
            assert app.screen.__class__.__name__ == "MappingsScreen"

            await pilot.press("escape")
            assert app.screen.__class__.__name__ == "HomeScreen"


def _make_bank_mapping() -> MagicMock:
    """Create a mock BankMapping with realistic field values."""
    mapping = MagicMock()
    mapping.bank_name = "danske_bank"
    mapping.date_format = "%d-%m-%Y"
    mapping.decimal_separator = ","
    mapping.default_currency = "DKK"
    mapping.blacklist_keywords = ["OVERFOERSEL"]

    cm = MagicMock()
    cm.date_column = "Dato"
    cm.amount_column = "Beløb"
    cm.description_columns = ["Tekst", "Tekst2"]
    cm.currency_column = None
    mapping.column_mapping = cm

    return mapping
