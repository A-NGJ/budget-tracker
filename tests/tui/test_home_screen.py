"""Pilot API tests for home screen navigation."""

from __future__ import annotations

import pytest

from budget_tracker.tui.app import BudgetTrackerApp


@pytest.mark.asyncio
class TestHomeScreen:
    """Tests for the home screen navigation."""

    @pytest.fixture
    def app(self) -> BudgetTrackerApp:
        return BudgetTrackerApp()

    async def test_home_screen_renders(self, app: BudgetTrackerApp) -> None:
        """Home screen displays title and menu items."""
        async with app.run_test():
            assert app.screen.__class__.__name__ == "HomeScreen"
            assert app.screen.query_one("#title")

    async def test_quit_key(self, app: BudgetTrackerApp) -> None:
        """Pressing Q exits the app."""
        async with app.run_test() as pilot:
            await pilot.press("q")

    async def test_process_key_pushes_file_selection(self, app: BudgetTrackerApp) -> None:
        """Pressing P navigates to file selection screen."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert app.screen.__class__.__name__ == "FileSelectionScreen"

    async def test_blacklist_key_pushes_placeholder(self, app: BudgetTrackerApp) -> None:
        """Pressing B navigates to placeholder screen."""
        async with app.run_test() as pilot:
            await pilot.press("b")
            assert app.screen.__class__.__name__ == "PlaceholderScreen"

    async def test_mappings_key_pushes_placeholder(self, app: BudgetTrackerApp) -> None:
        """Pressing M navigates to placeholder screen."""
        async with app.run_test() as pilot:
            await pilot.press("m")
            assert app.screen.__class__.__name__ == "PlaceholderScreen"

    async def test_clear_cache_key_pushes_placeholder(self, app: BudgetTrackerApp) -> None:
        """Pressing C navigates to placeholder screen."""
        async with app.run_test() as pilot:
            await pilot.press("c")
            assert app.screen.__class__.__name__ == "PlaceholderScreen"

    async def test_escape_from_file_selection_returns_home(self, app: BudgetTrackerApp) -> None:
        """Pressing Escape on file selection screen returns to home."""
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert app.screen.__class__.__name__ == "FileSelectionScreen"
            await pilot.press("escape")
            assert app.screen.__class__.__name__ == "HomeScreen"

    async def test_help_overlay_opens_and_closes(self, app: BudgetTrackerApp) -> None:
        """Pressing ? opens help overlay, Escape closes it."""
        async with app.run_test() as pilot:
            await pilot.press("question_mark")
            assert app.screen.__class__.__name__ == "HelpOverlay"
            await pilot.press("escape")
            assert app.screen.__class__.__name__ == "HomeScreen"

    async def test_pipeline_state_exists(self, app: BudgetTrackerApp) -> None:
        """App has a PipelineState instance."""
        async with app.run_test():
            assert hasattr(app, "pipeline_state")
            assert app.pipeline_state.files == []
            assert app.pipeline_state.period is None
