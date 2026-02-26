from decimal import Decimal
from io import StringIO

from rich.console import Console

from budget_tracker.analytics.models import (
    AnalyticsPeriod,
    AnalyticsResult,
    CategoryRow,
    MonthRow,
    SourceRow,
    SummaryData,
)
from budget_tracker.exporters.terminal_renderer import TerminalRenderer


def _make_console() -> Console:
    return Console(file=StringIO(), force_terminal=True, width=100)


def _make_result(**overrides: object) -> AnalyticsResult:
    period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
    defaults: dict[str, object] = {
        "summary": SummaryData(
            total_transactions=10,
            total_income=Decimal("5000"),
            total_expenses=Decimal("-3000"),
            net=Decimal("2000"),
            avg_transaction=Decimal("-300"),
            period=period,
        ),
        "category_data": [
            CategoryRow(
                category="Groceries",
                total=Decimal("-2000"),
                percentage=66.7,
                transaction_count=5,
                subcategories=[],
            ),
            CategoryRow(
                category="Transport",
                total=Decimal("-1000"),
                percentage=33.3,
                transaction_count=5,
                subcategories=[],
            ),
        ],
        "monthly_data": [
            MonthRow(
                year=2024,
                month=1,
                label="Jan 2024",
                income=Decimal("2500"),
                expenses=Decimal("-1500"),
                net=Decimal("1000"),
                transaction_count=5,
            ),
            MonthRow(
                year=2024,
                month=2,
                label="Feb 2024",
                income=Decimal("2500"),
                expenses=Decimal("-1500"),
                net=Decimal("1000"),
                transaction_count=5,
            ),
        ],
        "source_data": [
            SourceRow(
                source="Danske Bank",
                total_income=Decimal("3000"),
                total_expenses=Decimal("-2000"),
                transaction_count=6,
            ),
            SourceRow(
                source="Lunar",
                total_income=Decimal("2000"),
                total_expenses=Decimal("-1000"),
                transaction_count=4,
            ),
        ],
        "period": period,
    }
    defaults.update(overrides)
    return AnalyticsResult(**defaults)  # type: ignore[arg-type]


def _get_output(console: Console) -> str:
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue()


class TestSummaryPanel:
    def test_summary_panel(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result()

        renderer.render(result)
        output = _get_output(console)

        assert "All Time" in output
        assert "10" in output
        assert "5,000.00" in output
        assert "3,000.00" in output
        assert "2,000.00" in output

    def test_summary_panel_negative_net(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        period = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
        result = _make_result(
            summary=SummaryData(
                total_transactions=5,
                total_income=Decimal("1000"),
                total_expenses=Decimal("-3000"),
                net=Decimal("-2000"),
                avg_transaction=Decimal("-600"),
                period=period,
            ),
        )

        renderer.render(result)
        output = _get_output(console)

        assert "-2,000.00" in output


class TestCategoryTable:
    def test_category_table(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result()

        renderer.render(result)
        output = _get_output(console)

        assert "Expenses by Category" in output
        assert "Groceries" in output
        assert "Transport" in output
        assert "2,000.00" in output
        assert "66.7%" in output
        assert "33.3%" in output
        assert "█" in output

    def test_category_table_empty(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result(category_data=[])

        renderer.render(result)
        output = _get_output(console)

        assert "Expenses by Category" not in output


class TestMonthlyChart:
    def test_monthly_chart_renders(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result()

        renderer.render(result)
        output = _get_output(console)

        assert "Income" in output
        assert "Expenses" in output

    def test_monthly_chart_skipped_single_month(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result(
            monthly_data=[
                MonthRow(
                    year=2024,
                    month=1,
                    label="Jan 2024",
                    income=Decimal("2500"),
                    expenses=Decimal("-1500"),
                    net=Decimal("1000"),
                    transaction_count=5,
                ),
            ],
        )

        renderer.render(result)
        output = _get_output(console)

        # Chart title should not appear with only 1 month
        assert "Monthly Income vs Expenses" not in output


class TestSourceTable:
    def test_source_table_multiple_sources(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result()

        renderer.render(result)
        output = _get_output(console)

        assert "Transactions by Source" in output
        assert "Danske Bank" in output
        assert "Lunar" in output
        assert "3,000.00" in output
        assert "2,000.00" in output

    def test_source_table_single_source_hidden(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result(
            source_data=[
                SourceRow(
                    source="Danske Bank",
                    total_income=Decimal("5000"),
                    total_expenses=Decimal("-3000"),
                    transaction_count=10,
                ),
            ],
        )

        renderer.render(result)
        output = _get_output(console)

        assert "Transactions by Source" not in output


class TestFullRender:
    def test_full_render(self) -> None:
        console = _make_console()
        renderer = TerminalRenderer(console)
        result = _make_result()

        renderer.render(result)
        output = _get_output(console)

        # Summary panel
        assert "All Time" in output
        assert "5,000.00" in output

        # Category table
        assert "Expenses by Category" in output
        assert "Groceries" in output

        # Monthly chart (2 months present)
        assert "Income" in output

        # Source table (2 sources present)
        assert "Transactions by Source" in output
        assert "Danske Bank" in output
