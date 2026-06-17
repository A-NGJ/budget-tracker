"""FastAPI application factory exposing BudgetService read paths."""

from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Query

from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.api.dependencies import get_service
from budget_tracker.api.schemas import (
    AnalyticsSchema,
    HealthSchema,
    TransactionSchema,
)
from budget_tracker.services.budget_service import BudgetService

ServiceDep = Annotated[BudgetService, Depends(get_service)]


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(title="Budget Tracker API", version="0.1.0")

    @app.get("/api/health", response_model=HealthSchema)
    def health() -> HealthSchema:
        """Liveness probe."""
        return HealthSchema(status="ok")

    @app.get("/api/transactions", response_model=list[TransactionSchema])
    def list_transactions(  # noqa: PLR0913
        service: ServiceDep,
        source: Annotated[str | None, Query()] = None,
        category: Annotated[str | None, Query()] = None,
        subcategory: Annotated[str | None, Query()] = None,
        from_date: Annotated[date | None, Query()] = None,
        to_date: Annotated[date | None, Query()] = None,
        keyword: Annotated[str | None, Query()] = None,
    ) -> list[TransactionSchema]:
        """Return stored transactions matching the provided filters."""
        transactions = service.get_filtered_transactions(
            source=source,
            category=category,
            subcategory=subcategory,
            from_date=from_date,
            to_date=to_date,
            keyword=keyword,
        )
        return [TransactionSchema.model_validate(t) for t in transactions]

    @app.get("/api/transactions/count")
    def transaction_count(service: ServiceDep) -> int:
        """Return the total number of stored transactions."""
        return service.transaction_count()

    @app.get("/api/analytics", response_model=AnalyticsSchema)
    def analytics(  # noqa: PLR0913
        service: ServiceDep,
        from_date: Annotated[date | None, Query()] = None,
        to_date: Annotated[date | None, Query()] = None,
        label: Annotated[str | None, Query()] = None,
        source: Annotated[str | None, Query()] = None,
        category: Annotated[str | None, Query()] = None,
        subcategory: Annotated[str | None, Query()] = None,
        keyword: Annotated[str | None, Query()] = None,
    ) -> AnalyticsSchema:
        """Compute analytics over filtered transactions for the given period."""
        transactions = service.get_filtered_transactions(
            source=source,
            category=category,
            subcategory=subcategory,
            from_date=from_date,
            to_date=to_date,
            keyword=keyword,
        )
        period = AnalyticsPeriod(
            from_date=from_date,
            to_date=to_date,
            label=label or "All Time",
        )
        result = service.compute_analytics(transactions, period)
        return AnalyticsSchema.model_validate(result)

    @app.get("/api/filters/sources", response_model=list[str])
    def filter_sources(service: ServiceDep) -> list[str]:
        """Return the distinct transaction sources."""
        return service.get_transaction_sources()

    @app.get("/api/filters/categories", response_model=list[str])
    def filter_categories(service: ServiceDep) -> list[str]:
        """Return the distinct transaction categories."""
        return service.get_transaction_categories()

    @app.get(
        "/api/filters/categories/{category}/subcategories",
        response_model=list[str],
    )
    def filter_subcategories(service: ServiceDep, category: str) -> list[str]:
        """Return the distinct subcategories for a category."""
        return service.get_transaction_subcategories(category)

    return app


app = create_app()
