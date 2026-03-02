from budget_tracker.tui.app import BudgetTrackerApp

__all__ = ["BudgetTrackerApp", "main"]


def main() -> None:
    """Launch the Budget Tracker TUI application."""
    app = BudgetTrackerApp()
    app.run()
