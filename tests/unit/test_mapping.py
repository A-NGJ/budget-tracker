from pathlib import Path

import yaml

from budget_tracker.cli.mapping import load_mapping, save_mapping
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


class TestBankMappingYAML:
    def test_save_mapping_creates_yaml_file(self, tmp_path: Path) -> None:
        """Test that save_mapping creates a YAML file."""
        banks_dir = tmp_path / "banks"
        mapping = BankMapping(
            bank_name="test_bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_columns=["Desc"],
            ),
        )

        save_mapping(mapping, banks_dir)

        yaml_file = banks_dir / "test_bank.yaml"
        assert yaml_file.exists()

        with yaml_file.open() as f:
            data = yaml.safe_load(f)
        assert data["bank_name"] == "test_bank"

    def test_load_mapping_reads_yaml_file(self, tmp_path: Path) -> None:
        """Test that load_mapping reads YAML file."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        yaml_file = banks_dir / "test_bank.yaml"
        yaml_file.write_text(
            yaml.safe_dump(
                {
                    "bank_name": "test_bank",
                    "column_mapping": {
                        "date_column": "Date",
                        "amount_column": "Amount",
                        "description_columns": ["Desc"],
                    },
                }
            )
        )

        mapping = load_mapping("test_bank", banks_dir)

        assert mapping is not None
        assert mapping.bank_name == "test_bank"

    def test_load_mapping_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Test that load_mapping returns None for missing bank."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        mapping = load_mapping("non_existent_bank", banks_dir)

        assert mapping is None
