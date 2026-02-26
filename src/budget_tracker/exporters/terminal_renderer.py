from __future__ import annotations

from typing import TYPE_CHECKING

import plotext as plt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from budget_tracker.analytics.models import AnalyticsResult, CategoryRow, MonthRow, SourceRow

MAX_BAR_WIDTH = 20


class TerminalRenderer:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def render(self, result: AnalyticsResult) -> None:
        self._render_summary_panel(result)
        self._render_category_table(result.category_data)
        self._render_monthly_chart(result.monthly_data)
        self._render_source_table(result.source_data)

    def _render_summary_panel(self, result: AnalyticsResult) -> None:
        summary = result.summary
        net_style = "green" if summary.net >= 0 else "red"

        text = Text()
        text.append(f"  Transactions:  {summary.total_transactions}\n")
        text.append(f"  Income:        {summary.total_income:,.2f} DKK\n", style="green")
        text.append(f"  Expenses:      {summary.total_expenses:,.2f} DKK\n", style="red")
        text.append(f"  Net:           {summary.net:,.2f} DKK", style=net_style)

        panel = Panel(text, title=f"Analytics: {result.period.label}", expand=False)
        self._console.print(panel)

    def _render_category_table(self, category_data: list[CategoryRow]) -> None:
        if not category_data:
            return

        table = Table(title="Expenses by Category", expand=False)
        table.add_column("Category", style="cyan")
        table.add_column("Amount (DKK)", justify="right")
        table.add_column("%", justify="right")
        table.add_column("", justify="left")  # bar column

        max_pct = category_data[0].percentage if category_data else 1.0

        for row in category_data:
            bar_len = int(row.percentage / max_pct * MAX_BAR_WIDTH) if max_pct > 0 else 0
            bar = "█" * bar_len
            table.add_row(
                row.category,
                f"{row.total:,.2f}",
                f"{row.percentage:.1f}%",
                bar,
            )

        self._console.print(table)

    def _render_monthly_chart(self, monthly_data: list[MonthRow]) -> None:
        if len(monthly_data) <= 1:
            return

        labels = [row.label for row in monthly_data]
        income_vals = [float(row.income) for row in monthly_data]
        expense_vals = [float(abs(row.expenses)) for row in monthly_data]

        plt.clear_figure()
        plt.theme("clear")
        width = min(self._console.width, 120)
        plt.plot_size(width, 15)
        plt.title("Monthly Income vs Expenses")
        plt.multiple_bar(
            labels,
            [income_vals, expense_vals],
            labels=["Income", "Expenses"],
            color=["green", "red"],
        )

        chart_str = plt.build()
        self._console.print(Text.from_ansi(chart_str))

    def _render_source_table(self, source_data: list[SourceRow]) -> None:
        if len(source_data) < 2:
            return

        table = Table(title="Transactions by Source", expand=False)
        table.add_column("Source", style="cyan")
        table.add_column("Income", justify="right", style="green")
        table.add_column("Expenses", justify="right", style="red")
        table.add_column("#", justify="right")

        for row in source_data:
            table.add_row(
                row.source,
                f"{row.total_income:,.2f}",
                f"{row.total_expenses:,.2f}",
                str(row.transaction_count),
            )

        self._console.print(table)
