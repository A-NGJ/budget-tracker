from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    CategoryRow,
    MonthRow,
    SourceRow,
    SubcategoryRow,
    SummaryData,
)

if TYPE_CHECKING:
    from budget_tracker.models.transaction import StandardTransaction


class AnalyticsEngine:
    def compute(
        self,
        transactions: list[StandardTransaction],
        period: AnalyticsPeriod,
    ) -> AnalyticsResult:
        filtered = self._filter(transactions, period)
        label = self._compute_label(filtered, period)
        actual_period = AnalyticsPeriod(
            from_date=period.from_date,
            to_date=period.to_date,
            label=label,
        )
        return AnalyticsResult(
            summary=self._compute_summary(filtered, actual_period),
            category_data=self._compute_category_data(filtered),
            monthly_data=self._compute_monthly_data(filtered),
            source_data=self._compute_source_data(filtered),
            period=actual_period,
        )

    def _filter(
        self,
        transactions: list[StandardTransaction],
        period: AnalyticsPeriod,
    ) -> list[StandardTransaction]:
        result = []
        for t in transactions:
            if period.from_date is not None and t.date < period.from_date:
                continue
            if period.to_date is not None and t.date > period.to_date:
                continue
            result.append(t)
        return result

    def _compute_label(
        self,
        filtered: list[StandardTransaction],
        period: AnalyticsPeriod,
    ) -> str:
        if not filtered:
            return "No data"
        actual_min = min(t.date for t in filtered)
        actual_max = max(t.date for t in filtered)
        from_d = period.from_date if period.from_date is not None else actual_min
        to_d = period.to_date if period.to_date is not None else actual_max
        from_label = date(from_d.year, from_d.month, 1).strftime("%b %Y")
        to_label = date(to_d.year, to_d.month, 1).strftime("%b %Y")
        return from_label if from_label == to_label else f"{from_label} - {to_label}"

    def _compute_summary(
        self,
        filtered: list[StandardTransaction],
        period: AnalyticsPeriod,
    ) -> SummaryData:
        income = sum((t.amount for t in filtered if t.amount > 0), Decimal(0))
        expenses = sum((t.amount for t in filtered if t.amount < 0), Decimal(0))
        expense_count = sum(1 for t in filtered if t.amount < 0)
        avg = expenses / expense_count if expense_count > 0 else Decimal(0)
        return SummaryData(
            total_transactions=len(filtered),
            total_income=income,
            total_expenses=expenses,
            net=income + expenses,
            avg_transaction=avg,
            period=period,
        )

    def _compute_category_data(
        self,
        filtered: list[StandardTransaction],
    ) -> list[CategoryRow]:
        expenses = [t for t in filtered if t.amount < 0]
        if not expenses:
            return []
        total_expenses = sum(t.amount for t in expenses)

        cat_totals: dict[str, Decimal] = defaultdict(Decimal)
        cat_counts: dict[str, int] = defaultdict(int)
        sub_totals: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        sub_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for t in expenses:
            cat_totals[t.category] += t.amount
            cat_counts[t.category] += 1
            sub = t.subcategory or "Uncategorized"
            sub_totals[t.category][sub] += t.amount
            sub_counts[t.category][sub] += 1

        rows: list[CategoryRow] = []
        for cat, total in cat_totals.items():
            pct = float(abs(total) / abs(total_expenses) * 100) if total_expenses != 0 else 0.0
            subcats = [
                SubcategoryRow(
                    subcategory=sub,
                    total=sub_totals[cat][sub],
                    transaction_count=sub_counts[cat][sub],
                )
                for sub in sub_totals[cat]
            ]
            subcats.sort(key=lambda r: r.total)
            rows.append(
                CategoryRow(
                    category=cat,
                    total=total,
                    percentage=pct,
                    transaction_count=cat_counts[cat],
                    subcategories=subcats,
                )
            )
        rows.sort(key=lambda r: r.total)
        return rows

    def _compute_monthly_data(
        self,
        filtered: list[StandardTransaction],
    ) -> list[MonthRow]:
        monthly_income: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
        monthly_expenses: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
        monthly_counts: dict[tuple[int, int], int] = defaultdict(int)

        for t in filtered:
            key = (t.date.year, t.date.month)
            if t.amount > 0:
                monthly_income[key] += t.amount
            elif t.amount < 0:
                monthly_expenses[key] += t.amount
            monthly_counts[key] += 1

        keys = sorted(set(monthly_income) | set(monthly_expenses) | set(monthly_counts))
        rows: list[MonthRow] = []
        for year, month in keys:
            inc = monthly_income[(year, month)]
            exp = monthly_expenses[(year, month)]
            label = date(year, month, 1).strftime("%b %Y")
            rows.append(
                MonthRow(
                    year=year,
                    month=month,
                    label=label,
                    income=inc,
                    expenses=exp,
                    net=inc + exp,
                    transaction_count=monthly_counts[(year, month)],
                )
            )
        return rows

    def _compute_source_data(
        self,
        filtered: list[StandardTransaction],
    ) -> list[SourceRow]:
        src_income: dict[str, Decimal] = defaultdict(Decimal)
        src_expenses: dict[str, Decimal] = defaultdict(Decimal)
        src_counts: dict[str, int] = defaultdict(int)

        for t in filtered:
            if t.amount > 0:
                src_income[t.source] += t.amount
            elif t.amount < 0:
                src_expenses[t.source] += t.amount
            src_counts[t.source] += 1

        sources = sorted(set(src_income) | set(src_expenses))
        return [
            SourceRow(
                source=src,
                total_income=src_income[src],
                total_expenses=src_expenses[src],
                transaction_count=src_counts[src],
            )
            for src in sources
        ]
