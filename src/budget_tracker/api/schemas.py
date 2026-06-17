"""Pydantic response schemas for the API layer.

These mirror the domain dataclasses (``AnalyticsResult`` tree) and the
``StandardTransaction`` model, using ``from_attributes`` so FastAPI can
serialize the domain objects directly.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HealthSchema(BaseModel):
    """Health-check response."""

    status: str


class TransactionSchema(BaseModel):
    """A single stored transaction."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    category: str
    subcategory: str | None = None
    amount: Decimal
    source: str
    description: str | None = None


class AnalyticsPeriodSchema(BaseModel):
    """The period an analytics result covers."""

    model_config = ConfigDict(from_attributes=True)

    from_date: date | None
    to_date: date | None
    label: str


class SubcategoryRowSchema(BaseModel):
    """Per-subcategory expense aggregation."""

    model_config = ConfigDict(from_attributes=True)

    subcategory: str
    total: Decimal
    transaction_count: int


class CategoryRowSchema(BaseModel):
    """Per-category expense aggregation."""

    model_config = ConfigDict(from_attributes=True)

    category: str
    total: Decimal
    percentage: float
    transaction_count: int
    subcategories: list[SubcategoryRowSchema] = Field(default_factory=list)


class MonthRowSchema(BaseModel):
    """Per-month income/expense aggregation."""

    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int
    label: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    transaction_count: int


class SourceRowSchema(BaseModel):
    """Per-source income/expense aggregation."""

    model_config = ConfigDict(from_attributes=True)

    source: str
    total_income: Decimal
    total_expenses: Decimal
    transaction_count: int


class SummarySchema(BaseModel):
    """Top-level totals for an analytics result."""

    model_config = ConfigDict(from_attributes=True)

    total_transactions: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    avg_transaction: Decimal
    period: AnalyticsPeriodSchema


class AnalyticsSchema(BaseModel):
    """Full analytics result: summary plus category/monthly/source breakdowns."""

    model_config = ConfigDict(from_attributes=True)

    summary: SummarySchema
    category_data: list[CategoryRowSchema]
    monthly_data: list[MonthRowSchema]
    source_data: list[SourceRowSchema]
    period: AnalyticsPeriodSchema
