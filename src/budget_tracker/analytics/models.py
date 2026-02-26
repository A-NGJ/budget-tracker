from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from decimal import Decimal


@dataclass
class AnalyticsPeriod:
    from_date: date | None  # None = beginning of data
    to_date: date | None  # None = end of data
    label: str  # e.g., "Jan 2024 - Dec 2024"


@dataclass
class SubcategoryRow:
    subcategory: str
    total: Decimal  # always negative (expense sum)
    transaction_count: int


@dataclass
class CategoryRow:
    category: str
    total: Decimal  # always negative (expense sum)
    percentage: float  # of total expenses (0-100)
    transaction_count: int
    subcategories: list[SubcategoryRow] = field(default_factory=list)


@dataclass
class MonthRow:
    year: int
    month: int
    label: str  # e.g., "Jan 2024"
    income: Decimal
    expenses: Decimal  # always negative
    net: Decimal
    transaction_count: int


@dataclass
class SourceRow:
    source: str
    total_income: Decimal
    total_expenses: Decimal  # always negative
    transaction_count: int


@dataclass
class SummaryData:
    total_transactions: int
    total_income: Decimal
    total_expenses: Decimal  # always negative
    net: Decimal
    avg_transaction: Decimal  # avg expense = total_expenses / expense_count
    period: AnalyticsPeriod


@dataclass
class AnalyticsResult:
    summary: SummaryData
    category_data: list[CategoryRow]
    monthly_data: list[MonthRow]
    source_data: list[SourceRow]
    period: AnalyticsPeriod
