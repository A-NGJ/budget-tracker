from __future__ import annotations

from typing import TYPE_CHECKING, Any

import xlsxwriter

if TYPE_CHECKING:
    from pathlib import Path

    from budget_tracker.analytics.models import AnalyticsResult
    from budget_tracker.config.settings import Settings
    from budget_tracker.models.transaction import StandardTransaction


class ExcelExporter:
    """Export transactions and analytics to a formatted .xlsx workbook with charts."""

    def __init__(
        self,
        settings: Settings,
        analytics_result: AnalyticsResult,
        output_file: Path | None = None,
    ) -> None:
        self.output_dir = settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = output_file or (self.output_dir / settings.default_output_filename)
        self.analytics = analytics_result

    def export(self, transactions: list[StandardTransaction]) -> str:
        """Export transactions and analytics to a 5-sheet Excel workbook.

        Args:
            transactions: List of standardized transactions (Sheet 1).

        Returns:
            Path to created file as string.
        """
        workbook = xlsxwriter.Workbook(str(self.output_file))
        formats = self._create_formats(workbook)

        self._write_transactions_sheet(workbook, transactions, formats)
        self._write_summary_sheet(workbook, formats)
        self._write_category_sheet(workbook, formats)
        self._write_monthly_sheet(workbook, formats)
        self._write_source_sheet(workbook, formats)

        workbook.close()
        return str(self.output_file)

    # ── Format helpers ───────────────────────────────────────────────

    def _create_formats(self, workbook: xlsxwriter.Workbook) -> dict[str, Any]:
        header = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#4472C4",
                "font_color": "#FFFFFF",
                "border": 1,
            }
        )
        money = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        percent = workbook.add_format({"num_format": "0.0%", "border": 1})
        cell = workbook.add_format({"border": 1})
        alt_row = workbook.add_format({"bg_color": "#F2F2F2", "border": 1})
        alt_money = workbook.add_format(
            {"bg_color": "#F2F2F2", "num_format": "#,##0.00", "border": 1}
        )
        green = workbook.add_format(
            {"num_format": "#,##0.00", "font_color": "#008000", "bold": True}
        )
        red = workbook.add_format(
            {"num_format": "#,##0.00", "font_color": "#FF0000", "bold": True}
        )
        title = workbook.add_format({"bold": True, "font_size": 14})
        label = workbook.add_format({"bold": True})
        return {
            "header": header,
            "money": money,
            "percent": percent,
            "cell": cell,
            "alt_row": alt_row,
            "alt_money": alt_money,
            "green": green,
            "red": red,
            "title": title,
            "label": label,
        }

    # ── Sheet 1: Transactions ────────────────────────────────────────

    def _write_transactions_sheet(
        self,
        workbook: xlsxwriter.Workbook,
        transactions: list[StandardTransaction],
        formats: dict[str, Any],
    ) -> None:
        ws = workbook.add_worksheet("Transactions")
        columns = [
            "Transaction ID",
            "Date",
            "Description",
            "Category",
            "Subcategory",
            "Amount (DKK)",
            "Source",
        ]

        for col, name in enumerate(columns):
            ws.write(0, col, name, formats["header"])

        sorted_txns = sorted(transactions, key=lambda t: t.date)

        for row_idx, t in enumerate(sorted_txns, start=1):
            fmt = formats["alt_row"] if row_idx % 2 == 0 else formats["cell"]
            money_fmt = formats["alt_money"] if row_idx % 2 == 0 else formats["money"]

            ws.write(row_idx, 0, t.transaction_id, fmt)
            ws.write(row_idx, 1, t.date.strftime("%Y-%m-%d"), fmt)
            ws.write(row_idx, 2, t.description, fmt)
            ws.write(row_idx, 3, t.category, fmt)
            ws.write(row_idx, 4, t.subcategory or "", fmt)
            ws.write_number(row_idx, 5, float(t.amount), money_fmt)
            ws.write(row_idx, 6, t.source, fmt)

        ws.autofilter(0, 0, len(sorted_txns), len(columns) - 1)

        # Auto-fit column widths (approximate)
        col_widths = [16, 12, 30, 18, 18, 14, 16]
        for col, width in enumerate(col_widths):
            ws.set_column(col, col, width)

    # ── Sheet 2: Summary ─────────────────────────────────────────────

    def _write_summary_sheet(
        self,
        workbook: xlsxwriter.Workbook,
        formats: dict[str, Any],
    ) -> None:
        ws = workbook.add_worksheet("Summary")
        summary = self.analytics.summary

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 18)

        ws.write(0, 0, summary.period.label, formats["title"])

        metrics: list[tuple[str, float, Any]] = [
            ("Total Transactions", float(summary.total_transactions), formats["label"]),
            ("Total Income", float(summary.total_income), formats["green"]),
            ("Total Expenses", float(summary.total_expenses), formats["red"]),
            (
                "Net",
                float(summary.net),
                formats["green"] if summary.net >= 0 else formats["red"],
            ),
            ("Avg Transaction", float(summary.avg_transaction), formats["red"]),
        ]

        for i, (label, value, val_fmt) in enumerate(metrics, start=2):
            ws.write(i, 0, label, formats["label"])
            if label == "Total Transactions":
                ws.write(i, 1, int(value))
            else:
                ws.write_number(i, 1, value, val_fmt)

    # ── Sheet 3: Category Breakdown ──────────────────────────────────

    def _write_category_sheet(
        self,
        workbook: xlsxwriter.Workbook,
        formats: dict[str, Any],
    ) -> None:
        ws = workbook.add_worksheet("Category Breakdown")
        headers = ["Category", "Amount (DKK)", "% of Total", "# Transactions"]

        for col, name in enumerate(headers):
            ws.write(0, col, name, formats["header"])

        # category_data is already sorted by total (most negative first)
        cat_data = self.analytics.category_data
        for row_idx, cat in enumerate(cat_data, start=1):
            fmt = formats["alt_row"] if row_idx % 2 == 0 else formats["cell"]
            money_fmt = formats["alt_money"] if row_idx % 2 == 0 else formats["money"]
            pct_fmt = formats["percent"]

            ws.write(row_idx, 0, cat.category, fmt)
            ws.write_number(row_idx, 1, float(cat.total), money_fmt)
            ws.write_number(row_idx, 2, cat.percentage / 100.0, pct_fmt)
            ws.write_number(row_idx, 3, cat.transaction_count, fmt)

        ws.set_column(0, 0, 22)
        ws.set_column(1, 1, 16)
        ws.set_column(2, 2, 12)
        ws.set_column(3, 3, 16)

        # Pie chart
        if cat_data:
            last_row = len(cat_data)
            chart = workbook.add_chart({"type": "pie"})
            chart.add_series(
                {
                    "name": "Expense by Category",
                    "categories": ["Category Breakdown", 1, 0, last_row, 0],
                    "values": ["Category Breakdown", 1, 1, last_row, 1],
                    "data_labels": {"percentage": True, "category": True},
                }
            )
            chart.set_title({"name": "Expense Distribution by Category"})
            chart.set_size({"width": 520, "height": 360})
            ws.insert_chart("F2", chart)

        # Subcategory detail tables below main table
        sub_start_row = len(cat_data) + 3
        for cat in cat_data:
            if not cat.subcategories:
                continue
            ws.write(sub_start_row, 0, cat.category, formats["title"])
            sub_start_row += 1
            sub_headers = ["Subcategory", "Amount (DKK)", "# Transactions"]
            for col, name in enumerate(sub_headers):
                ws.write(sub_start_row, col, name, formats["header"])
            sub_start_row += 1
            for sub in cat.subcategories:
                ws.write(sub_start_row, 0, sub.subcategory, formats["cell"])
                ws.write_number(sub_start_row, 1, float(sub.total), formats["money"])
                ws.write_number(sub_start_row, 2, sub.transaction_count, formats["cell"])
                sub_start_row += 1
            sub_start_row += 1  # blank row between categories

    # ── Sheet 4: Monthly Trends ──────────────────────────────────────

    def _write_monthly_sheet(
        self,
        workbook: xlsxwriter.Workbook,
        formats: dict[str, Any],
    ) -> None:
        ws = workbook.add_worksheet("Monthly Trends")
        headers = ["Month", "Income", "Expenses", "Net", "# Transactions"]

        for col, name in enumerate(headers):
            ws.write(0, col, name, formats["header"])

        monthly = self.analytics.monthly_data
        for row_idx, m in enumerate(monthly, start=1):
            fmt = formats["alt_row"] if row_idx % 2 == 0 else formats["cell"]
            money_fmt = formats["alt_money"] if row_idx % 2 == 0 else formats["money"]

            ws.write(row_idx, 0, m.label, fmt)
            ws.write_number(row_idx, 1, float(m.income), money_fmt)
            ws.write_number(row_idx, 2, float(m.expenses), money_fmt)
            ws.write_number(row_idx, 3, float(m.net), money_fmt)
            ws.write_number(row_idx, 4, m.transaction_count, fmt)

        ws.set_column(0, 0, 14)
        ws.set_column(1, 4, 16)

        # Bar + line chart
        if monthly:
            last_row = len(monthly)

            bar_chart = workbook.add_chart({"type": "column"})
            bar_chart.add_series(
                {
                    "name": "Income",
                    "categories": ["Monthly Trends", 1, 0, last_row, 0],
                    "values": ["Monthly Trends", 1, 1, last_row, 1],
                    "fill": {"color": "#70AD47"},
                }
            )
            bar_chart.add_series(
                {
                    "name": "Expenses",
                    "categories": ["Monthly Trends", 1, 0, last_row, 0],
                    "values": ["Monthly Trends", 1, 2, last_row, 2],
                    "fill": {"color": "#FF4444"},
                }
            )
            bar_chart.set_title({"name": "Monthly Income vs Expenses"})
            bar_chart.set_y_axis({"name": "Amount (DKK)"})
            bar_chart.set_size({"width": 720, "height": 400})

            line_chart = workbook.add_chart({"type": "line"})
            line_chart.add_series(
                {
                    "name": "Net",
                    "categories": ["Monthly Trends", 1, 0, last_row, 0],
                    "values": ["Monthly Trends", 1, 3, last_row, 3],
                    "line": {"color": "#4472C4", "width": 2.5},
                    "marker": {"type": "circle", "size": 5},
                }
            )

            bar_chart.combine(line_chart)
            ws.insert_chart("A" + str(last_row + 3), bar_chart)

    # ── Sheet 5: Source Analysis ─────────────────────────────────────

    def _write_source_sheet(
        self,
        workbook: xlsxwriter.Workbook,
        formats: dict[str, Any],
    ) -> None:
        ws = workbook.add_worksheet("Source Analysis")
        headers = ["Source", "Income", "Expenses", "Total", "# Transactions"]

        for col, name in enumerate(headers):
            ws.write(0, col, name, formats["header"])

        sources = self.analytics.source_data
        for row_idx, s in enumerate(sources, start=1):
            fmt = formats["alt_row"] if row_idx % 2 == 0 else formats["cell"]
            money_fmt = formats["alt_money"] if row_idx % 2 == 0 else formats["money"]

            total = float(s.total_income) + float(s.total_expenses)
            ws.write(row_idx, 0, s.source, fmt)
            ws.write_number(row_idx, 1, float(s.total_income), money_fmt)
            ws.write_number(row_idx, 2, float(s.total_expenses), money_fmt)
            ws.write_number(row_idx, 3, total, money_fmt)
            ws.write_number(row_idx, 4, s.transaction_count, fmt)

        ws.set_column(0, 0, 20)
        ws.set_column(1, 4, 16)

        # Horizontal bar chart
        if sources:
            last_row = len(sources)
            chart = workbook.add_chart({"type": "bar"})
            chart.add_series(
                {
                    "name": "Expenses",
                    "categories": ["Source Analysis", 1, 0, last_row, 0],
                    "values": ["Source Analysis", 1, 2, last_row, 2],
                    "fill": {"color": "#FF4444"},
                }
            )
            chart.set_title({"name": "Spending by Source"})
            chart.set_x_axis({"name": "Amount (DKK)"})
            chart.set_size({"width": 520, "height": 360})
            ws.insert_chart("G2", chart)
