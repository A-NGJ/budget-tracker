"""
CLI integration tests for the budget tracker.

These tests verify CLI argument parsing, component wiring, and data flow.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from budget_tracker.cli.main import app, create_app
from budget_tracker.config.settings import Settings
from budget_tracker.models.transaction import StandardTransaction


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Create isolated test settings."""
    settings = Settings()
    settings.config_dir = tmp_path / "config"
    settings.data_dir = tmp_path / "data"
    settings.output_dir = tmp_path / "output"
    settings.banks_dir = tmp_path / "banks"
    settings.output_dir.mkdir(parents=True)
    settings.category_mappings_file = tmp_path / "category_mappings.yaml"
    settings.banks_dir.mkdir(parents=True)
    return settings


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create sample CSV file"""
    csv_content = """Date,Amount,Description
2024-01-15,-100.00,Cafe Central Copenhagen
2025-10-11,-24.00,Metro Ticket
2025-10-12,5000.00,Salary Payment"""
    csv_file = tmp_path / "bank1.csv"
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def make_bank_mappings(settings: Settings) -> None:
    """Create sample bank mapping YAML filess"""
    mapping_data_bank1 = {
        "bank_name": "bank1",
        "column_mapping": {
            "date_column": "Date",
            "amount_column": "Amount",
            "description_columns": ["Description"],
            "currency_column": None,
        },
        "date_format": "%Y-%m-%d",
        "decimal_separator": ".",
        "default_currency": "DKK",
    }

    mapping_data_bank2 = {
        "bank_name": "bank2",
        "column_mapping": {
            "date_column": "Date",
            "amount_column": "Amount",
            "description_columns": ["Description"],
            "currency_column": None,
        },
        "date_format": "%Y-%m-%d",
        "decimal_separator": ".",
        "default_currency": "DKK",
    }

    yaml_file_bank1 = settings.banks_dir / "bank1.yaml"
    yaml_file_bank1.write_text(yaml.safe_dump(mapping_data_bank1))
    yaml_file_bank2 = settings.banks_dir / "bank2.yaml"
    yaml_file_bank2.write_text(yaml.safe_dump(mapping_data_bank2))


class TestEndToEnd:
    def test_cli_help(self, cli_runner: CliRunner) -> None:
        """Test that CLI help displays correctly"""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Bank Statement Normalizer" in result.output

    def test_process_command_help(self, cli_runner: CliRunner) -> None:
        """Test that process command help displays correctly"""
        result = cli_runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "Process bank statement CSV files" in result.output

    def test_list_mappings_empty(self, cli_runner: CliRunner, settings: Settings) -> None:
        """Test listing mappings when none exist"""
        # Create app with injected test settings
        test_app = create_app(settings)

        result = cli_runner.invoke(test_app, ["list-mappings"])
        assert result.exit_code == 0
        assert "No saved mappings found" in result.output

    def test_list_mappings_with_data(
        self,
        cli_runner: CliRunner,
        settings: Settings,
        make_bank_mappings: None,  # noqa: ARG002
    ) -> None:
        """Test listing mappings when they exist"""
        # Create app with injected test settings
        test_app = create_app(settings)

        result = cli_runner.invoke(test_app, ["list-mappings"])
        assert result.exit_code == 0
        assert "bank1" in result.output
        assert "bank2" in result.output

    @patch("budget_tracker.cli.main.confirm_transfers")
    @patch("budget_tracker.cli.main.categorize_transactions")
    def test_full_processing_flow(  # noqa: PLR0913
        self,
        mock_categorize: MagicMock,
        mock_confirm_transfers: MagicMock,
        cli_runner: CliRunner,
        settings: Settings,
        sample_csv: Path,
        make_bank_mappings: None,  # noqa: ARG002
    ) -> None:
        """Test complete flow from CSV to output."""
        # Setup mocks
        mock_confirm_transfers.return_value = ([], [])
        mock_categorize.return_value = [
            StandardTransaction(
                date=date(2024, 1, 15),
                category="Food & Drinks",
                subcategory="Restaurants",
                amount=Decimal("-100.00"),
                source="bank1",
                description="Cafe Central Copenhagen",
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                subcategory="Public Transport",
                amount=Decimal("-24.00"),
                source="bank1",
                description="Metro Ticket",
            ),
            StandardTransaction(
                date=date(2025, 10, 12),
                category="Income",
                subcategory="Salary",
                amount=Decimal("5000.00"),
                source="bank1",
                description="Salary Payment",
            ),
        ]

        output_file = settings.output_dir / "output.csv"
        test_app = create_app(settings)

        result = cli_runner.invoke(
            test_app,
            ["process", str(sample_csv), "-b", "bank1", "--output", str(output_file)],
        )

        # Verify successful execution
        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Verify output file exists
        assert output_file.exists()

        # Verify output content
        df = pd.read_csv(output_file)
        assert len(df) >= 1  # At least one transaction processed
        assert "Date" in df.columns
        assert "Category" in df.columns
        assert "Amount (DKK)" in df.columns
        assert "Source" in df.columns

    @patch("budget_tracker.cli.main.confirm_transfers")
    @patch("budget_tracker.cli.main.categorize_transactions")
    def test_process_with_transfers(  # noqa: PLR0913
        self,
        mock_categorize: MagicMock,
        mock_confirm_transfers: MagicMock,
        cli_runner: CliRunner,
        settings: Settings,
        sample_csv: Path,
        make_bank_mappings: None,  # noqa: ARG002
    ) -> None:
        """Test that transfer detection is called during processing."""

        # 1. Setup mock_confirm_transfers to return empty (no confirmed transfers)
        mock_confirm_transfers.return_value = ([], [])

        # 2. Setup mock categorize_transactions
        mock_categorize.return_value = [
            StandardTransaction(
                date=date(2024, 1, 15),
                category="Food & Drinks",
                subcategory="Restaurants",
                amount=Decimal("-100.00"),
                source="bank1",
                description="Cafe Central Copenhagen",
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                subcategory="Public Transport",
                amount=Decimal("-24.00"),
                source="bank1",
                description="Metro Ticket",
            ),
            StandardTransaction(
                date=date(2025, 10, 12),
                category="Income",
                subcategory="Salary",
                amount=Decimal("5000.00"),
                source="bank1",
                description="Salary Payment",
            ),
            StandardTransaction(
                date=date(2024, 1, 15),
                category="Food & Drinks",
                subcategory="Restaurants",
                amount=Decimal("100.00"),
                source="bank2",
                description="Transfer from checking",
            ),
        ]

        # 3. Create second CSV file (incoming transfer from different bank)
        second_csv = settings.output_dir / "bank2.csv"
        second_csv.write_text("Date,Amount,Description\n2024-01-15,100.00,Transfer from checking\n")

        # 4. Create app with test settings and invoke CLI
        test_app = create_app(settings)
        _ = cli_runner.invoke(
            test_app,
            ["process", str(sample_csv), str(second_csv), "-b", "bank1", "-b", "bank2"],
        )

        # 5. Assertions
        # Verify confirm_transfers was called (transfer detection ran)
        mock_confirm_transfers.assert_called_once()

        # Verify the call received TransferPair objects
        call_args = mock_confirm_transfers.call_args[0][0]  # First positional arg
        assert isinstance(call_args, list)
        # Should detect the 100.00 transfer pair (same amount, same date, different banks)
        assert len(call_args) >= 1


class TestCLIValidation:
    def test_process_nonexistent_file(self, cli_runner: CliRunner) -> None:
        """Test that processing a non-existent file shows an error"""
        result = cli_runner.invoke(app, ["process", "nonexistent.csv", "--banks", "test_bank"])
        assert result.exit_code == 1

    def test_process_requires_files(self, cli_runner: CliRunner) -> None:
        """Test that process command requires at least one file"""
        result = cli_runner.invoke(app, ["process"])
        assert result.exit_code != 0

    def test_process_requires_banks_flag(self, cli_runner: CliRunner) -> None:
        """Test that process command requires --banks flag"""
        result = cli_runner.invoke(app, ["process", "somefile.csv"])
        assert result.exit_code != 0
