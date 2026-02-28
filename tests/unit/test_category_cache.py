"""Unit tests for CategoryCache."""

from pathlib import Path

import yaml

from budget_tracker.config.settings import Settings
from budget_tracker.services.category_cache import CategoryCache


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


class TestLoad:
    def test_load_empty_when_no_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("anything") is None

    def test_load_valid_entries(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Cafe Central": {
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                    },
                    "DSB Train": {
                        "category": "Transportation",
                        "subcategory": "Public Transport",
                    },
                }
            )
        )
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("Cafe Central") == ("Food & Drinks", "Restaurants")
        assert cache.get("DSB Train") == ("Transportation", "Public Transport")

    def test_load_filters_invalid_category(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Unknown Shop": {
                        "category": "NonExistent",
                        "subcategory": None,
                    },
                }
            )
        )
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("Unknown Shop") is None

    def test_load_filters_invalid_subcategory(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Some Shop": {
                        "category": "Food & Drinks",
                        "subcategory": "WrongSub",
                    },
                }
            )
        )
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("Some Shop") is None

    def test_load_malformed_yaml(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text("- just a list\n- not a dict\n")
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("anything") is None

    def test_load_malformed_entry(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file.write_text(
            yaml.safe_dump(
                {
                    "Good Entry": {
                        "category": "Food & Drinks",
                        "subcategory": "Groceries",
                    },
                    "Bad Entry": "not a dict",
                }
            )
        )
        cache = CategoryCache(settings)
        cache.load()
        assert cache.get("Good Entry") == ("Food & Drinks", "Groceries")
        assert cache.get("Bad Entry") is None


class TestGetAndSet:
    def test_get_hit(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache._cache["NETTO"] = ("Food & Drinks", "Groceries")
        assert cache.get("NETTO") == ("Food & Drinks", "Groceries")

    def test_get_miss(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        assert cache.get("nonexistent") is None

    def test_set_and_get(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache.set("NETTO", "Food & Drinks", "Groceries")
        assert cache.get("NETTO") == ("Food & Drinks", "Groceries")


class TestSave:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache.set("NETTO", "Food & Drinks", "Groceries")
        cache.set("DSB", "Transportation", None)
        cache.save()

        raw = yaml.safe_load(settings.category_mappings_file.read_text())
        assert raw["NETTO"] == {"category": "Food & Drinks", "subcategory": "Groceries"}
        assert raw["DSB"] == {"category": "Transportation", "subcategory": None}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        settings.category_mappings_file = tmp_path / "nested" / "deep" / "mappings.yaml"
        cache = CategoryCache(settings)
        cache.set("NETTO", "Food & Drinks", "Groceries")
        cache.save()

        assert settings.category_mappings_file.exists()


class TestClear:
    def test_clear_removes_entries_and_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache.set("NETTO", "Food & Drinks", "Groceries")
        cache.save()
        assert settings.category_mappings_file.exists()

        cache.clear()
        assert cache.get("NETTO") is None
        assert not settings.category_mappings_file.exists()

    def test_clear_no_file(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        cache = CategoryCache(settings)
        cache.set("NETTO", "Food & Drinks", "Groceries")
        # Don't save — no file on disk
        cache.clear()
        assert cache.get("NETTO") is None
