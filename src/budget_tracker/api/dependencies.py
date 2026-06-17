"""FastAPI dependency providers for the API layer."""

from budget_tracker.config.settings import get_settings
from budget_tracker.services.budget_service import BudgetService


def get_service() -> BudgetService:
    """Provide a ``BudgetService`` backed by the application settings.

    Tests override this via ``app.dependency_overrides`` to inject a service
    bound to isolated, seeded settings.
    """
    return BudgetService(get_settings())
