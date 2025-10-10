from pathlib import Path

import pytest

from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.parsers.csv_parser import CSVParser, detect_delimiter


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file for testing"""
    csv_content = """Dato,Beløb,Tekst
10-10-2025,125.50,Cafe X
11-10-2025,-50.00,Supermarket"""
    csv_file = tmp_path / "test_bank.csv"
    csv_file.write_text(csv_content)
    return csv_file


class TestCSVParser:
    def test_detect_delimiter_comma(self, sample_csv: Path) -> None:
        """Test delimiter detection for comma-separated files"""
        delimiter = detect_delimiter(sample_csv)
        assert delimiter == ","

    def test_detect_delimiter_semicolon(self, tmp_path: Path) -> None:
        """Test delimiter detection for semicolon-separated files"""
        csv_content = """Date;Amount;Description
2025-10-10;125.50;Purchase"""
        csv_file = tmp_path / "semicolon.csv"
        csv_file.write_text(csv_content)
        delimiter = detect_delimiter(csv_file)
        assert delimiter == ";"

    def test_parse_csv_without_mapping(self, sample_csv: Path) -> None:
        """Test parsing CSV and detecting columns"""
        parser = CSVParser()
        df, columns = parser.parse_file(sample_csv)
        assert len(df) == 2
        assert "Dato" in columns
        assert "Beløb" in columns
        assert "Tekst" in columns

    def test_load_with_mapping(self, sample_csv: Path) -> None:
        """Test loading CSV with pre-configured mapping"""
        mapping = BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Dato", amount_column="Beløb", description_column="Tekst"
            ),
            date_format="%d-%m-%Y",
        )
        parser = CSVParser()
        raw_transactions = parser.load_with_mapping(sample_csv, mapping)
        assert len(raw_transactions) == 2
        assert raw_transactions[0].data["Dato"] == "10-10-2025"

    def test_handle_malformed_csv(self, tmp_path: Path) -> None:
        """Test graceful handling of malformed CSV"""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("not,a,proper\ncsv,file")
        parser = CSVParser()
        df, _ = parser.parse_file(bad_csv)
        assert df is not None  # Should not crash


class TestInteractiveMapping:
    def test_create_mapping_from_user_input(self) -> None:
        """Test creating mapping from simulated user selections"""
        # This will be implemented with Typer prompts
        pass
