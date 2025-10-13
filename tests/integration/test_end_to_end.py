"""
End-to-end integration tests for the budget tracker CLI.

Note: These tests require Ollama to be running with the llama3.2:3b model.
Run: ollama serve (in background)
Run: ollama pull llama3.2:3b
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from budget_tracker.cli.main import app

runner = CliRunner()


class TestEndToEnd:
    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create sample CSV file"""
        csv_content = """Date,Amount,Description
2025-10-10,-125.50,Cafe Central Copenhagen
2025-10-11,-24.00,Metro Ticket
2025-10-12,5000.00,Salary Payment"""
        csv_file = tmp_path / "test_bank.csv"
        csv_file.write_text(csv_content)
        return csv_file

    @pytest.fixture
    def sample_mapping(self, tmp_path: Path) -> Path:
        """Create a sample bank mapping file"""
        mappings_file = tmp_path / "bank_mappings.json"
        mapping = {
            "test_bank": {
                "bank_name": "test_bank",
                "column_mapping": {
                    "date_column": "Date",
                    "amount_column": "Amount",
                    "description_column": "Description",
                    "currency_column": None,
                },
                "date_format": "%Y-%m-%d",
                "decimal_separator": ".",
                "default_currency": "DKK",
            }
        }
        mappings_file.write_text(json.dumps(mapping, indent=2))
        return mappings_file

    def test_cli_help(self) -> None:
        """Test that CLI help displays correctly"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Bank Statement Normalizer" in result.output

    def test_process_command_help(self) -> None:
        """Test that process command help displays correctly"""
        result = runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "Process bank statement CSV files" in result.output

    def test_list_mappings_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing mappings when none exist"""
        # Set up temporary config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        mappings_file = config_dir / "bank_mappings.json"

        # Monkeypatch settings to use temp directory
        from budget_tracker.config import settings as settings_module

        monkeypatch.setattr(settings_module.settings, "mappings_file", mappings_file)

        result = runner.invoke(app, ["list-mappings"])
        assert result.exit_code == 0
        assert "No saved mappings found" in result.output

    def test_list_mappings_with_data(
        self, tmp_path: Path, sample_mapping: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test listing mappings when they exist"""
        # Monkeypatch settings to use temp directory
        from budget_tracker.config import settings as settings_module

        monkeypatch.setattr(settings_module.settings, "mappings_file", sample_mapping)

        result = runner.invoke(app, ["list-mappings"])
        assert result.exit_code == 0
        assert "test_bank" in result.output

    @pytest.mark.skip(reason="Requires interactive input and Ollama to be running")
    def test_full_processing_flow(
        self, sample_csv: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test complete flow from CSV to output.

        Note: This test requires:
        1. Ollama to be running (ollama serve)
        2. Model to be available (ollama pull llama3.2:3b)
        3. Interactive prompts to be mocked

        This is skipped by default but can be run manually for verification.
        """
        output_file = tmp_path / "output.csv"

        # This would need proper mocking of interactive prompts
        # and Ollama connection

        result = runner.invoke(app, ["process", str(sample_csv), "--output", str(output_file)])

        # Verify output file exists
        assert output_file.exists()

        # Verify output content
        df = pd.read_csv(output_file)
        assert len(df) >= 1  # At least one transaction processed
        assert "Date" in df.columns
        assert "Category" in df.columns
        assert "Amount (DKK)" in df.columns
        assert "Source" in df.columns


class TestCLIValidation:
    def test_process_nonexistent_file(self) -> None:
        """Test that processing a non-existent file shows an error"""
        result = runner.invoke(app, ["process", "nonexistent.csv"])
        assert result.exit_code == 1

    def test_process_requires_files(self) -> None:
        """Test that process command requires at least one file"""
        result = runner.invoke(app, ["process"])
        assert result.exit_code != 0
