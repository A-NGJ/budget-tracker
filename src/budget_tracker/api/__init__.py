"""FastAPI backend exposing BudgetService read paths as typed JSON."""

from budget_tracker.api.app import create_app

__all__ = ["create_app"]
