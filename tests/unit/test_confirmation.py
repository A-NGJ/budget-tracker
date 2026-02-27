"""Unit tests for category persistence in confirmation.py."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from budget_tracker.cli.confirmation import (
    _load_category_mappings,
    _save_category_mappings,
    categorize_transactions,
)
from budget_tracker.config.settings import Settings
from budget_tracker.parsers.csv_parser import ParsedTransaction


def _make_settings(tmp_path: Path) -> Settings:
    """Create isolated test settings with a categories file."""
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


class TestLoadCategoryMappings:
    def test_load_empty_when_no_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        result = _load_category_mappings(settings)
        assert result == {}

    def test_load_valid_mappings(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                    },
                    "Metro Ticket": {
                        "category": "Transportation",
                        "subcategory": "Public Transport",
                    },
                }
            )
        )
        result = _load_category_mappings(settings)
        assert result == {
            "Cafe Central": ("Food & Drinks", "Restaurants"),
            "Metro Ticket": ("Transportation", "Public Transport"),
        }

    def test_load_skips_invalid_category(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "NonExistent",
                        "subcategory": None,
                    },
                }
            )
        )
        result = _load_category_mappings(settings)
        assert result == {}

    def test_load_skips_invalid_subcategory(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "InvalidSubcat",
                    },
                }
            )
        )
        result = _load_category_mappings(settings)
        assert result == {}

    def test_load_handles_corrupted_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text("just a string\n")
        result = _load_category_mappings(settings)
        assert result == {}


class TestSaveCategoryMappings:
    def test_save_creates_directory(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file = tmp_path / "nested" / "dir" / "mappings.yaml"
        cache: dict[str, tuple[str, str | None]] = {
            "Cafe Central": ("Food & Drinks", "Restaurants"),
        }
        _save_category_mappings(settings, cache)
        assert settings.category_mappings_file.exists()

    def test_save_writes_valid_yaml(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache: dict[str, tuple[str, str | None]] = {
            "Cafe Central": ("Food & Drinks", "Restaurants"),
            "Metro Ticket": ("Transportation", None),
        }
        _save_category_mappings(settings, cache)
        data = yaml.safe_load(settings.category_mappings_file.read_text())
        assert data == {
            "Cafe Central": {"category": "Food & Drinks", "subcategory": "Restaurants"},
            "Metro Ticket": {"category": "Transportation", "subcategory": None},
        }

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        _save_category_mappings(settings, {"Old": ("Food & Drinks", None)})
        _save_category_mappings(settings, {"New": ("Transportation", "Public Transport")})
        data = yaml.safe_load(settings.category_mappings_file.read_text())
        assert "Old" not in data
        assert data["New"] == {
            "category": "Transportation",
            "subcategory": "Public Transport",
        }


class TestCategorizeTransactionsIntegration:
    @patch("budget_tracker.cli.confirmation.select_option")
    def test_categorize_uses_persisted_mappings(
        self,
        mock_select: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Pre-populated YAML file auto-categorizes without prompting."""
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                    },
                }
            )
        )

        converter = MagicMock()
        converter.convert.return_value = Decimal("100")

        transactions = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Cafe Central",
                source="bank1",
                source_file="test.csv",
            )
        ]

        result = categorize_transactions(settings, transactions, converter)

        assert len(result) == 1
        assert result[0].category == "Food & Drinks"
        assert result[0].subcategory == "Restaurants"
        mock_select.assert_not_called()

    @patch("budget_tracker.cli.confirmation.select_option")
    def test_no_cache_skips_persisted_mappings(
        self,
        mock_select: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With no_cache=True, cached mappings are ignored and user is prompted."""
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                    },
                }
            )
        )

        mock_select.side_effect = ["Transportation", "Public Transport"]

        converter = MagicMock()
        converter.convert.return_value = Decimal("100")

        transactions = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Cafe Central",
                source="bank1",
                source_file="test.csv",
            )
        ]

        result = categorize_transactions(settings, transactions, converter, no_cache=True)

        assert len(result) == 1
        assert result[0].category == "Transportation"
        assert result[0].subcategory == "Public Transport"
        assert mock_select.call_count == 2  # category + subcategory prompts

    @patch("budget_tracker.cli.confirmation.select_option")
    def test_no_cache_preserves_existing_and_overwrites_overlap(
        self,
        mock_select: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With no_cache=True, new choices overwrite overlapping keys but preserve others."""
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                    },
                    "Metro Ticket": {
                        "category": "Transportation",
                        "subcategory": "Public Transport",
                    },
                }
            )
        )

        # Re-categorize "Cafe Central" with a different choice
        mock_select.side_effect = ["Transportation", "Public Transport"]

        converter = MagicMock()
        converter.convert.return_value = Decimal("100")

        transactions = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("100"),
                currency="DKK",
                description="Cafe Central",
                source="bank1",
                source_file="test.csv",
            )
        ]

        categorize_transactions(settings, transactions, converter, no_cache=True)

        data = yaml.safe_load(settings.category_mappings_file.read_text())
        # Overlapping key overwritten with new value
        assert data["Cafe Central"] == {
            "category": "Transportation",
            "subcategory": "Public Transport",
        }
        # Non-overlapping key preserved
        assert data["Metro Ticket"] == {
            "category": "Transportation",
            "subcategory": "Public Transport",
        }

    @patch("budget_tracker.cli.confirmation.select_option")
    def test_no_cache_still_deduplicates_within_session(
        self,
        mock_select: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With no_cache=True, duplicate descriptions in same session reuse the first choice."""
        settings = _make_settings(tmp_path)

        # Only one pair of prompts (category + subcategory) for the first occurrence
        mock_select.side_effect = ["Food & Drinks", "Groceries"]

        converter = MagicMock()
        converter.convert.return_value = Decimal("50")

        transactions = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("50"),
                currency="DKK",
                description="Supermarket",
                source="bank1",
                source_file="test.csv",
            ),
            ParsedTransaction(
                date=date(2026, 1, 2),
                amount=Decimal("30"),
                currency="DKK",
                description="Supermarket",
                source="bank1",
                source_file="test.csv",
            ),
        ]

        result = categorize_transactions(settings, transactions, converter, no_cache=True)

        assert len(result) == 2
        assert result[0].category == "Food & Drinks"
        assert result[1].category == "Food & Drinks"
        # Only prompted once (2 select calls for category + subcategory)
        assert mock_select.call_count == 2

    @patch("budget_tracker.cli.confirmation.select_option")
    def test_categorize_saves_new_mapping(
        self,
        mock_select: MagicMock,
        tmp_path: Path,
    ) -> None:
        """New description triggers prompt and saves mapping to disk."""
        settings = _make_settings(tmp_path)

        # First call returns category, second returns subcategory
        mock_select.side_effect = ["Food & Drinks", "Groceries"]

        converter = MagicMock()
        converter.convert.return_value = Decimal("50")

        transactions = [
            ParsedTransaction(
                date=date(2026, 1, 1),
                amount=Decimal("50"),
                currency="DKK",
                description="Supermarket",
                source="bank1",
                source_file="test.csv",
            )
        ]

        result = categorize_transactions(settings, transactions, converter)

        assert len(result) == 1
        assert result[0].category == "Food & Drinks"
        assert result[0].subcategory == "Groceries"

        # Verify YAML file was written
        assert settings.category_mappings_file.exists()
        data = yaml.safe_load(settings.category_mappings_file.read_text())
        assert data["Supermarket"] == {
            "category": "Food & Drinks",
            "subcategory": "Groceries",
        }
