"""Budget Tracker TUI application."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App

from budget_tracker.tui.screens.home import HomeScreen
from budget_tracker.tui.screens.placeholder import PlaceholderScreen
from budget_tracker.tui.state import PipelineState


class BudgetTrackerApp(App[None]):
    """Budget Tracker TUI application."""

    TITLE = "Budget Tracker"
    CSS_PATH = "styles/app.tcss"

    SCREENS: ClassVar[dict[str, type]] = {
        "home": HomeScreen,
        "placeholder": PlaceholderScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.pipeline_state = PipelineState()

    def on_mount(self) -> None:
        self.push_screen("home")
