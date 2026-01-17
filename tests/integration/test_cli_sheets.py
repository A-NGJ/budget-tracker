from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from budget_tracker.categorizer.llm_categorizer import CategoryResult
from budget_tracker.cli.main import create_app
from budget_tracker.config.settings import Settings
from budget_tracker.parsers.csv_parser import ParsedTransaction


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        banks_dir=tmp_path / "banks",
        google_credentials_dir=tmp_path / ".budget-tracker",
        google_credentials_file=tmp_path / ".budget-tracker" / "credentials.json",
        google_token_file=tmp_path / ".budget-tracker" / "token.json",
    )


class TestSheetsFlag:
    def test_sheets_flag_existing(self, runner: CliRunner, settings: Settings) -> None:
        """Test that --sheets flag is recognized"""
        app = create_app(settings)
        result = runner.invoke(app, ["process", "--help"])

        assert "--sheets" in result.output
        assert "Export to Google Sheets" in result.output

    @patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
    @patch("budget_tracker.cli.main.GoogleSheetsExporter")
    @patch("budget_tracker.cli.main.CSVExporter")
    @patch("budget_tracker.cli.main.LLMCategorizer")
    @patch("budget_tracker.cli.main.CSVParser")
    def test_sheets_flag_triggers_sheets_export(  # noqa: PLR0913
        self,
        mock_parser: MagicMock,
        mock_categorizer: MagicMock,
        mock_csv_exporter: MagicMock,
        mock_sheets_exporter: MagicMock,
        mock_ollama: MagicMock,  # noqa: ARG002
        runner: CliRunner,
        settings: Settings,
        tmp_path: Path,
    ) -> None:
        """Test that --sheets flag triggers Google Sheets export"""
        # Setup
        settings.banks_dir.mkdir(parents=True, exist_ok=True)

        # Create test bank mapping
        bank_file = settings.banks_dir / "test_bank.yaml"
        bank_file.write_text("""
bank_name: test_bank
column_mapping:
  date_column: Date
  amount_column: Amount
  description_columns: [Description]
date_format: "%Y-%m-%d"
decimal_separator: "."
default_currency: DKK
""")

        # Create test CSV
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Date,Amount,Description\n2026-01-01,100,Test\n")

        # Mock parser to return transactions
        mock_parser_instance = MagicMock()
        mock_parser_instance.load_with_mapping.return_value = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Test",
                source="test_bank",
                source_file="test.csv",
            )
        ]
        mock_parser.return_value = mock_parser_instance

        mock_cat_instance = MagicMock()
        mock_cat_instance.categorize.return_value = CategoryResult(
            category="Other",
            subcategory="Uncategorized",
            confidence=1.0,
            needs_confirmation=False,
        )
        mock_categorizer.return_value = mock_cat_instance

        # Mock exporters
        mock_csv_instance = MagicMock()
        mock_csv_instance.export.return_value = tmp_path / "output.csv"
        mock_csv_exporter.return_value = mock_csv_instance

        mock_sheets_instance = MagicMock()
        mock_sheets_instance.export.return_value = "Exportert 1 transaction"
        mock_sheets_exporter.return_value = mock_sheets_instance

        app = create_app(settings)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = Decimal("100")

        with (
            patch("budget_tracker.cli.main.CurrencyConverter", return_value=mock_converter),
            patch(
                "budget_tracker.cli.main.confirm_uncertain_categories", side_effect=lambda _, t: t
            ),
        ):
            _ = runner.invoke(
                app,
                ["process", str(test_csv), "-b", "test_bank", "--sheets"],
            )

        # Verify Google Sheets exporter was called
        mock_sheets_exporter.assert_called_once()
        mock_sheets_instance.export.assert_called_once()

    @patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
    @patch("budget_tracker.cli.main.GoogleSheetsExporter")
    @patch("budget_tracker.cli.main.CSVExporter")
    @patch("budget_tracker.cli.main.LLMCategorizer")
    @patch("budget_tracker.cli.main.CSVParser")
    def test_without_sheets_flag_no_sheets_export(  # noqa: PLR0913
        self,
        mock_parser: MagicMock,
        mock_categorizer: MagicMock,
        mock_csv_exporter: MagicMock,
        mock_sheets_exporter: MagicMock,
        mock_ollama: MagicMock,  # noqa: ARG002
        runner: CliRunner,
        settings: Settings,
        tmp_path: Path,
    ) -> None:
        """Test that without --sheets flag, only CSV export happens."""
        # Setup
        settings.banks_dir.mkdir(parents=True, exist_ok=True)

        # Create test bank mapping
        bank_file = settings.banks_dir / "test_bank.yaml"
        bank_file.write_text("""
bank_name: test_bank
column_mapping:
  date_column: Date
  amount_column: Amount
  description_columns: [Description]
date_format: "%Y-%m-%d"
decimal_separator: "."
default_currency: DKK
""")

        # Create test CSV
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Date,Amount,Description\n2026-01-01,100,Test\n")

        # Mock parser to return transactions
        mock_parser_instance = MagicMock()
        mock_parser_instance.load_with_mapping.return_value = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Test",
                source="test_bank",
                source_file="test.csv",
            )
        ]
        mock_parser.return_value = mock_parser_instance

        mock_cat_instance = MagicMock()
        mock_cat_instance.categorize.return_value = CategoryResult(
            category="Other",
            subcategory="Uncategorized",
            confidence=1.0,
            needs_confirmation=False,
        )
        mock_categorizer.return_value = mock_cat_instance

        # Mock exporters
        mock_csv_instance = MagicMock()
        mock_csv_instance.export.return_value = tmp_path / "output.csv"
        mock_csv_exporter.return_value = mock_csv_instance

        app = create_app(settings)

        mock_converter = MagicMock()
        mock_converter.convert.return_value = Decimal("100")

        with (
            patch("budget_tracker.cli.main.CurrencyConverter", return_value=mock_converter),
            patch(
                "budget_tracker.cli.main.confirm_uncertain_categories", side_effect=lambda _, t: t
            ),
        ):
            _ = runner.invoke(
                app,
                ["process", str(test_csv), "-b", "test_bank"],
            )

        # Verify Google Sheets exporter was not called
        mock_sheets_exporter.assert_not_called()
