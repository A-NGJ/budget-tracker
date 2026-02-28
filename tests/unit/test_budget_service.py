"""Unit tests for BudgetService facade."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from budget_tracker.config.settings import Settings
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.parsers.csv_parser import ParsedTransaction
from budget_tracker.services.budget_service import BudgetService


def _make_settings(tmp_path: Path) -> Settings:
    """Create isolated test settings."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    categories_file = config_dir / "categories.yaml"
    categories_file.write_text(
        yaml.safe_dump(
            {
                "categories": [
                    {
                        "name": "Food & Drinks",
                        "subcategories": ["Groceries", "Restaurants"],
                    },
                    {"name": "Transportation", "subcategories": ["Public Transport"]},
                    {"name": "Internal Transfer", "subcategories": ["Transfer"]},
                    {"name": "Other"},
                ]
            }
        )
    )
    return Settings(
        config_dir=config_dir,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        banks_dir=tmp_path / "banks",
        categories_file=categories_file,
        default_categories_file=categories_file,
        category_mappings_file=tmp_path / "category_mappings.yaml",
    )


def _make_mapping() -> BankMapping:
    return BankMapping(
        bank_name="test_bank",
        column_mapping=ColumnMapping(
            date_column="Date",
            amount_column="Amount",
            description_columns=["Text"],
        ),
        date_format="%Y-%m-%d",
        decimal_separator=".",
        default_currency="DKK",
    )


def _make_parsed() -> ParsedTransaction:
    return ParsedTransaction(
        date=date(2024, 1, 15),
        amount=Decimal("-150.00"),
        currency="DKK",
        description="NETTO",
        source="test_bank",
        source_file="test.csv",
    )


def _make_service(tmp_path: Path) -> BudgetService:
    settings = _make_settings(tmp_path)
    return BudgetService(settings)


class TestFileOperations:
    def test_detect_columns(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        with patch.object(service._parser, "parse_file", return_value=("df", ["A", "B"])) as mock:
            result = service.detect_columns(Path("test.csv"))
            mock.assert_called_once_with(Path("test.csv"))
            assert result == ("df", ["A", "B"])

    def test_parse_file(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        parsed = [_make_parsed()]
        with patch.object(service._parser, "load_with_mapping", return_value=parsed) as mock:
            result = service.parse_file(Path("test.csv"), mapping)
            mock.assert_called_once_with(Path("test.csv"), mapping)
            assert result == parsed


class TestBankMappingOperations:
    def test_load_mapping_found(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        # Save mapping to disk
        service._settings.banks_dir.mkdir(parents=True, exist_ok=True)
        mapping_file = service._settings.banks_dir / "test_bank.yaml"
        with mapping_file.open("w") as f:
            yaml.safe_dump(mapping.model_dump(), f)

        result = service.load_mapping("test_bank")
        assert result is not None
        assert result.bank_name == "test_bank"

    def test_load_mapping_not_found(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        result = service.load_mapping("nonexistent")
        assert result is None

    def test_save_mapping(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        service.save_mapping(mapping)

        mapping_file = service._settings.banks_dir / "test_bank.yaml"
        assert mapping_file.exists()
        data = yaml.safe_load(mapping_file.read_text())
        assert data["bank_name"] == "test_bank"

    def test_list_mappings(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        service._settings.banks_dir.mkdir(parents=True, exist_ok=True)
        (service._settings.banks_dir / "alpha.yaml").write_text("bank_name: alpha")
        (service._settings.banks_dir / "beta.yaml").write_text("bank_name: beta")

        result = service.list_mappings()
        assert result == ["alpha", "beta"]

    def test_list_mappings_no_dir(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        # banks_dir doesn't exist
        result = service.list_mappings()
        assert result == []


class TestTransferOperations:
    def test_detect_transfers(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        transactions = [_make_parsed()]
        with patch.object(
            service._transfer_detector, "detect", return_value=([], transactions)
        ) as mock:
            result = service.detect_transfers(transactions)
            mock.assert_called_once_with(transactions)
            assert result == ([], transactions)


class TestCurrencyAndTransactions:
    def test_convert_currency(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        with patch.object(
            service._currency_converter, "convert", return_value=Decimal("100.00")
        ) as mock:
            result = service.convert_currency(Decimal("15.00"), "EUR", date(2024, 1, 15))
            mock.assert_called_once_with(Decimal("15.00"), "EUR", "DKK", date(2024, 1, 15))
            assert result == Decimal("100.00")

    def test_create_transaction(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        parsed = _make_parsed()
        txn = service.create_transaction(parsed, "Food & Drinks", "Groceries", Decimal("-150.00"))
        assert txn.date == date(2024, 1, 15)
        assert txn.category == "Food & Drinks"
        assert txn.subcategory == "Groceries"
        assert txn.amount == Decimal("-150.00")
        assert txn.source == "test_bank"
        assert txn.description == "NETTO"

    def test_create_transfer_transaction(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        parsed = _make_parsed()
        with patch.object(service._currency_converter, "convert", return_value=Decimal("-150.00")):
            txn = service.create_transfer_transaction(parsed)
            assert txn.category == "Internal Transfer"
            assert txn.subcategory == "Transfer"
            assert txn.amount == Decimal("-150.00")
            assert txn.source == "test_bank"


class TestCategoryOperations:
    def test_load_categories(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        cats = service.load_categories()
        assert cats["Food & Drinks"] == ["Groceries", "Restaurants"]
        assert cats["Transportation"] == ["Public Transport"]
        assert cats["Other"] == []


class TestCacheDelegation:
    def test_cache_delegation(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)

        # Initially empty
        assert service.get_cached_category("NETTO") is None

        # Set and get
        service.cache_category("NETTO", "Food & Drinks", "Groceries")
        assert service.get_cached_category("NETTO") == ("Food & Drinks", "Groceries")

        # Save and verify persistence
        service.save_cache()
        assert service._settings.category_mappings_file.exists()

        # Clear
        service.clear_cache()
        assert service.get_cached_category("NETTO") is None
        assert not service._settings.category_mappings_file.exists()


class TestAnalytics:
    def test_compute_analytics(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mock_result = MagicMock()
        with patch.object(service._analytics_engine, "compute", return_value=mock_result) as mock:
            transactions = [MagicMock()]
            period = MagicMock()
            result = service.compute_analytics(transactions, period)
            mock.assert_called_once_with(transactions, period)
            assert result is mock_result


class TestExport:
    def test_export_excel(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        with patch("budget_tracker.services.budget_service.ExcelExporter") as mock_cls:
            mock_cls.return_value.export.return_value = "/output/file.xlsx"

            result = service.export_excel([], MagicMock(), Path("/output/file.xlsx"))
            mock_cls.assert_called_once()
            assert result == "/output/file.xlsx"

    def test_export_csv(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        with patch("budget_tracker.services.budget_service.CSVExporter") as mock_cls:
            mock_cls.return_value.export.return_value = "/output/file.csv"

            result = service.export_csv([], Path("/output/file.csv"))
            mock_cls.assert_called_once()
            assert result == "/output/file.csv"

    def test_export_google_sheets(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        with patch("budget_tracker.services.budget_service.GoogleSheetsExporter") as mock_cls:
            mock_cls.return_value.export.return_value = "https://sheets.google.com/..."

            result = service.export_google_sheets([], MagicMock())
            mock_cls.assert_called_once()
            assert result == "https://sheets.google.com/..."


class TestBlacklistOperations:
    def test_load_bank_blacklist(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        mapping.blacklist_keywords = ["VISA", "DANKORT"]
        service.save_mapping(mapping)

        result = service.load_bank_blacklist("test_bank")
        assert result == ["VISA", "DANKORT"]

    def test_load_bank_blacklist_no_mapping(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        result = service.load_bank_blacklist("nonexistent")
        assert result == []

    def test_add_blacklist_keyword(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        service.save_mapping(mapping)

        service.add_blacklist_keyword("test_bank", "VISA")
        updated = service.load_mapping("test_bank")
        assert updated is not None
        assert "VISA" in updated.blacklist_keywords

    def test_remove_blacklist_keyword(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        mapping = _make_mapping()
        mapping.blacklist_keywords = ["VISA", "DANKORT"]
        service.save_mapping(mapping)

        service.remove_blacklist_keyword("test_bank", "VISA")
        updated = service.load_mapping("test_bank")
        assert updated is not None
        assert "VISA" not in updated.blacklist_keywords
        assert "DANKORT" in updated.blacklist_keywords
