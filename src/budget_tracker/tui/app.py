"""Budget Tracker TUI application."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App

from budget_tracker.config.settings import get_settings
from budget_tracker.services.budget_service import BudgetService
from budget_tracker.tui.screens.categorization import CategorizationScreen
from budget_tracker.tui.screens.file_selection import FileSelectionScreen
from budget_tracker.tui.screens.home import HomeScreen
from budget_tracker.tui.screens.placeholder import PlaceholderScreen
from budget_tracker.tui.screens.transfer_review import TransferReviewScreen
from budget_tracker.tui.state import PipelineState


class BudgetTrackerApp(App[None]):
    """Budget Tracker TUI application."""

    TITLE = "Budget Tracker"
    CSS_PATH = "styles/app.tcss"

    SCREENS: ClassVar[dict[str, type]] = {
        "home": HomeScreen,
        "placeholder": PlaceholderScreen,
        "file_selection": FileSelectionScreen,
        "transfer_review": TransferReviewScreen,
        "categorization": CategorizationScreen,
    }

    def __init__(self, service: BudgetService | None = None) -> None:
        super().__init__()
        self._service = service
        self.pipeline_state = PipelineState()

    @property
    def service(self) -> BudgetService:
        if self._service is None:
            self._service = BudgetService(get_settings())
        return self._service

    def on_mount(self) -> None:
        self.push_screen("home")
