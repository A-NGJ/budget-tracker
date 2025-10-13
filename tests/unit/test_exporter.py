from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.models.transaction import StandardTransaction


class TestCSVExporter:
    @pytest.fixture
    def sample_transactions(self) -> list[StandardTransaction]:
        return [
            StandardTransaction(
                date=date(2025, 10, 10),
                category="Food & Drinks",
                subcategory="Restaurants",
                amount=Decimal("-125.50"),
                source="Danske Bank",
                description="Cafe Central",
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                subcategory="Public Transport",
                amount=Decimal("-24.00"),
                source="Nordea",
                description="Metro ticket",
            ),
        ]

    @pytest.fixture
    def exporter(self, tmp_path: Path) -> CSVExporter:
        return CSVExporter(output_dir=tmp_path)

    def test_export_to_csv(
        self,
        exporter: CSVExporter,
        sample_transactions: list[StandardTransaction],
        tmp_path: Path,
    ) -> None:
        """Test exporting transactions to CSV"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        assert output_file.exists()

        # Verify CSV content
        df = pd.read_csv(output_file)
        assert len(df) == 2
        assert "Date" in df.columns
        assert "Category" in df.columns
        assert "Amount (DKK)" in df.columns
        assert "Source" in df.columns

    def test_correct_column_order(
        self,
        exporter: CSVExporter,
        sample_transactions: list[StandardTransaction],
        tmp_path: Path,
    ) -> None:
        """Test that columns are in correct order"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        df = pd.read_csv(output_file)
        expected_columns = ["Date", "Category", "Amount (DKK)", "Source"]
        assert df.columns.tolist() == expected_columns

    def test_date_format_in_output(
        self,
        exporter: CSVExporter,
        sample_transactions: list[StandardTransaction],
        tmp_path: Path,
    ) -> None:
        """Test that dates are formatted correctly"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        df = pd.read_csv(output_file)
        assert df.iloc[0]["Date"] == "2025-10-10"

    def test_combine_multiple_sources(self, exporter: CSVExporter, tmp_path: Path) -> None:
        """Test combining transactions from multiple banks"""
        transactions = [
            StandardTransaction(
                date=date(2025, 10, 10),
                category="Food & Drinks",
                amount=Decimal("-100"),
                source="Bank A",
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                amount=Decimal("-50"),
                source="Bank B",
            ),
        ]

        output_file = tmp_path / "combined.csv"
        exporter.export(transactions, output_file)

        df = pd.read_csv(output_file)
        assert len(df) == 2
        assert set(df["Source"].unique()) == {"Bank A", "Bank B"}

    def test_sort_by_date(
        self,
        exporter: CSVExporter,
        sample_transactions: list[StandardTransaction],
        tmp_path: Path,
    ) -> None:
        """Test that output is sorted by date"""
        # Add transactions in reverse order
        unsorted = [sample_transactions[1], sample_transactions[0]]

        output_file = tmp_path / "sorted.csv"
        exporter.export(unsorted, output_file)

        df = pd.read_csv(output_file)
        dates = pd.to_datetime(df["Date"])
        assert dates.is_monotonic_increasing
