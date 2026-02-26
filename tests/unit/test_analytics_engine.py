from __future__ import annotations

from datetime import date
from decimal import Decimal

from budget_tracker.analytics.engine import AnalyticsEngine
from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.models.transaction import StandardTransaction


def make_tx(
    amount: str,
    category: str = "Food & Drinks",
    subcategory: str | None = "Groceries",
    source: str = "Danske Bank",
    date_str: str = "2024-01-15",
) -> StandardTransaction:
    return StandardTransaction.model_construct(
        date=date.fromisoformat(date_str),
        category=category,
        subcategory=subcategory,
        amount=Decimal(amount),
        source=source,
    )


def _open_period() -> AnalyticsPeriod:
    return AnalyticsPeriod(from_date=None, to_date=None, label="")


ENGINE = AnalyticsEngine()


# ---------------------------------------------------------------------------
# TestPeriodFiltering
# ---------------------------------------------------------------------------


class TestPeriodFiltering:
    def test_no_bounds_includes_all(self) -> None:
        txs = [make_tx("-10"), make_tx("-20", date_str="2024-06-01")]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_transactions == 2

    def test_from_date_excludes_earlier(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-01-01"),
            make_tx("-20", date_str="2024-03-01"),
        ]
        period = AnalyticsPeriod(from_date=date(2024, 2, 1), to_date=None, label="")
        result = ENGINE.compute(txs, period)
        assert result.summary.total_transactions == 1
        assert result.summary.total_expenses == Decimal("-20")

    def test_to_date_excludes_later(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-01-01"),
            make_tx("-20", date_str="2024-03-01"),
        ]
        period = AnalyticsPeriod(from_date=None, to_date=date(2024, 2, 1), label="")
        result = ENGINE.compute(txs, period)
        assert result.summary.total_transactions == 1
        assert result.summary.total_expenses == Decimal("-10")

    def test_both_bounds_inclusive(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-01-01"),
            make_tx("-20", date_str="2024-01-15"),
            make_tx("-30", date_str="2024-02-01"),
        ]
        period = AnalyticsPeriod(from_date=date(2024, 1, 1), to_date=date(2024, 1, 15), label="")
        result = ENGINE.compute(txs, period)
        assert result.summary.total_transactions == 2

    def test_empty_after_filtering(self) -> None:
        txs = [make_tx("-10", date_str="2024-01-01")]
        period = AnalyticsPeriod(from_date=date(2025, 1, 1), to_date=None, label="")
        result = ENGINE.compute(txs, period)
        assert result.summary.total_transactions == 0
        assert result.summary.total_expenses == Decimal("0")


# ---------------------------------------------------------------------------
# TestSummaryComputation
# ---------------------------------------------------------------------------


class TestSummaryComputation:
    def test_all_expenses_summary(self) -> None:
        txs = [make_tx("-100"), make_tx("-50")]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_income == Decimal("0")
        assert result.summary.total_expenses == Decimal("-150")
        assert result.summary.net == Decimal("-150")

    def test_all_income_summary(self) -> None:
        txs = [make_tx("1000", category="Income", subcategory=None)]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_income == Decimal("1000")
        assert result.summary.total_expenses == Decimal("0")
        assert result.summary.net == Decimal("1000")

    def test_mixed_summary(self) -> None:
        txs = [
            make_tx("1000", category="Income", subcategory=None),
            make_tx("-300"),
            make_tx("-200"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_income == Decimal("1000")
        assert result.summary.total_expenses == Decimal("-500")
        assert result.summary.net == Decimal("500")
        assert result.summary.total_transactions == 3

    def test_avg_is_expense_average_not_net_average(self) -> None:
        txs = [
            make_tx("1000", category="Income", subcategory=None),
            make_tx("-100"),
            make_tx("-200"),
        ]
        result = ENGINE.compute(txs, _open_period())
        # avg = -300 / 2 = -150
        assert result.summary.avg_transaction == Decimal("-150")

    def test_avg_zero_when_no_expenses(self) -> None:
        txs = [make_tx("500", category="Income", subcategory=None)]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.avg_transaction == Decimal("0")


# ---------------------------------------------------------------------------
# TestCategoryBreakdown
# ---------------------------------------------------------------------------


class TestCategoryBreakdown:
    def test_categories_expenses_only(self) -> None:
        txs = [
            make_tx("1000", category="Income", subcategory=None),
            make_tx("-50"),
        ]
        result = ENGINE.compute(txs, _open_period())
        categories = [r.category for r in result.category_data]
        assert "Income" not in categories
        assert "Food & Drinks" in categories

    def test_categories_sorted_largest_first(self) -> None:
        txs = [
            make_tx("-100", category="Food & Drinks"),
            make_tx("-300", category="Housing", subcategory="Rent"),
            make_tx("-50", category="Transport", subcategory="Bus"),
        ]
        result = ENGINE.compute(txs, _open_period())
        totals = [r.total for r in result.category_data]
        # Most negative first (ascending sort)
        assert totals == sorted(totals)

    def test_category_percentage(self) -> None:
        txs = [
            make_tx("-75", category="Food & Drinks"),
            make_tx("-25", category="Transport", subcategory="Bus"),
        ]
        result = ENGINE.compute(txs, _open_period())
        pct_map = {r.category: r.percentage for r in result.category_data}
        assert pct_map["Food & Drinks"] == 75.0
        assert pct_map["Transport"] == 25.0

    def test_subcategories_nested(self) -> None:
        txs = [
            make_tx("-50", category="Food & Drinks", subcategory="Groceries"),
            make_tx("-30", category="Food & Drinks", subcategory="Restaurants"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert len(result.category_data) == 1
        row = result.category_data[0]
        assert row.category == "Food & Drinks"
        sub_names = [s.subcategory for s in row.subcategories]
        assert "Groceries" in sub_names
        assert "Restaurants" in sub_names

    def test_none_subcategory_becomes_uncategorized(self) -> None:
        txs = [make_tx("-50", category="Food & Drinks", subcategory=None)]
        result = ENGINE.compute(txs, _open_period())
        row = result.category_data[0]
        assert row.subcategories[0].subcategory == "Uncategorized"

    def test_empty_categories_when_all_income(self) -> None:
        txs = [make_tx("500", category="Income", subcategory=None)]
        result = ENGINE.compute(txs, _open_period())
        assert result.category_data == []


# ---------------------------------------------------------------------------
# TestMonthlyData
# ---------------------------------------------------------------------------


class TestMonthlyData:
    def test_single_month(self) -> None:
        txs = [make_tx("-10"), make_tx("-20")]
        result = ENGINE.compute(txs, _open_period())
        assert len(result.monthly_data) == 1
        assert result.monthly_data[0].label == "Jan 2024"

    def test_multiple_months_sorted(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-03-01"),
            make_tx("-20", date_str="2024-01-01"),
        ]
        result = ENGINE.compute(txs, _open_period())
        labels = [m.label for m in result.monthly_data]
        assert labels == ["Jan 2024", "Mar 2024"]

    def test_cross_year_boundary(self) -> None:
        txs = [
            make_tx("-10", date_str="2023-12-15"),
            make_tx("-20", date_str="2024-01-15"),
        ]
        result = ENGINE.compute(txs, _open_period())
        labels = [m.label for m in result.monthly_data]
        assert labels == ["Dec 2023", "Jan 2024"]

    def test_income_and_expenses_separated_per_month(self) -> None:
        txs = [
            make_tx("1000", category="Income", subcategory=None, date_str="2024-01-05"),
            make_tx("-200", date_str="2024-01-10"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert len(result.monthly_data) == 1
        m = result.monthly_data[0]
        assert m.income == Decimal("1000")
        assert m.expenses == Decimal("-200")
        assert m.net == Decimal("800")


# ---------------------------------------------------------------------------
# TestSourceData
# ---------------------------------------------------------------------------


class TestSourceData:
    def test_single_source(self) -> None:
        txs = [make_tx("-100")]
        result = ENGINE.compute(txs, _open_period())
        assert len(result.source_data) == 1
        assert result.source_data[0].source == "Danske Bank"

    def test_multiple_sources(self) -> None:
        txs = [
            make_tx("-100", source="Danske Bank"),
            make_tx("-50", source="Revolut"),
        ]
        result = ENGINE.compute(txs, _open_period())
        sources = {r.source for r in result.source_data}
        assert sources == {"Danske Bank", "Revolut"}

    def test_source_income_expenses_separated(self) -> None:
        txs = [
            make_tx("1000", category="Income", subcategory=None, source="Danske Bank"),
            make_tx("-200", source="Danske Bank"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert len(result.source_data) == 1
        s = result.source_data[0]
        assert s.total_income == Decimal("1000")
        assert s.total_expenses == Decimal("-200")
        assert s.transaction_count == 2


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_transactions_returns_zeroed_result(self) -> None:
        result = ENGINE.compute([], _open_period())
        assert result.summary.total_transactions == 0
        assert result.summary.total_income == Decimal("0")
        assert result.summary.total_expenses == Decimal("0")
        assert result.summary.net == Decimal("0")
        assert result.summary.avg_transaction == Decimal("0")
        assert result.category_data == []
        assert result.monthly_data == []
        assert result.source_data == []

    def test_single_expense_transaction(self) -> None:
        txs = [make_tx("-42.50")]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_transactions == 1
        assert result.summary.total_expenses == Decimal("-42.50")
        assert result.summary.avg_transaction == Decimal("-42.50")
        assert len(result.category_data) == 1
        assert len(result.monthly_data) == 1
        assert len(result.source_data) == 1

    def test_single_income_transaction(self) -> None:
        txs = [make_tx("5000", category="Income", subcategory=None)]
        result = ENGINE.compute(txs, _open_period())
        assert result.summary.total_transactions == 1
        assert result.summary.total_income == Decimal("5000")
        assert result.summary.total_expenses == Decimal("0")
        assert result.category_data == []

    def test_period_label_computed_from_actual_range(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-03-01"),
            make_tx("-20", date_str="2024-06-01"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert result.period.label == "Mar 2024 - Jun 2024"

    def test_period_label_single_month(self) -> None:
        txs = [
            make_tx("-10", date_str="2024-05-01"),
            make_tx("-20", date_str="2024-05-15"),
        ]
        result = ENGINE.compute(txs, _open_period())
        assert result.period.label == "May 2024"

    def test_period_label_no_data(self) -> None:
        txs = [make_tx("-10", date_str="2024-01-01")]
        period = AnalyticsPeriod(from_date=date(2025, 1, 1), to_date=None, label="")
        result = ENGINE.compute(txs, period)
        assert result.period.label == "No data"
