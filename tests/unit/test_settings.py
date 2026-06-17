"""Unit tests for Settings configuration and data directory migration."""

from pathlib import Path
from unittest.mock import patch

from budget_tracker.config.settings import Settings, _maybe_migrate_data_dir


class TestSettingsDefaults:
    def test_default_dir_has_no_dot(self, monkeypatch) -> None:
        """Default data paths use ~/budget-tracker (no leading dot)."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert not str(s.transactions_file).endswith(".budget-tracker/transactions.json")
        assert not str(s.categories_file).endswith(".budget-tracker/categories.yaml")
        assert not str(s.category_mappings_file).endswith(".budget-tracker/category_mappings.yaml")
        assert not str(s.banks_dir).endswith(".budget-tracker/banks")

    def test_default_dir_uses_budget_tracker(self, monkeypatch) -> None:
        """Default data paths resolve under ~/budget-tracker."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert str(s.transactions_file).endswith("budget-tracker/transactions.json")
        assert str(s.categories_file).endswith("budget-tracker/categories.yaml")
        assert str(s.category_mappings_file).endswith("budget-tracker/category_mappings.yaml")
        assert str(s.banks_dir).endswith("budget-tracker/banks")


class TestMigrateDataDir:
    def test_migrate_data_dir_moves_old_to_new(self, tmp_path: Path) -> None:
        """Moves ~/.budget-tracker to ~/budget-tracker when old exists and new doesn't."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()
        (old / "transactions.json").write_text("[]")

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert new.exists()
        assert (new / "transactions.json").exists()
        assert not old.exists()

    def test_no_migration_when_new_already_exists(self, tmp_path: Path) -> None:
        """Does not move old dir when new dir already exists."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()
        new.mkdir()
        (old / "transactions.json").write_text("[]")

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert old.exists()
        assert new.exists()
        assert not (new / "transactions.json").exists()

    def test_no_migration_when_old_does_not_exist(self, tmp_path: Path) -> None:
        """Does not raise when old dir is absent (fresh install)."""
        new = tmp_path / "budget-tracker"

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert not new.exists()

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        """Calling _maybe_migrate_data_dir twice is safe."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()
            _maybe_migrate_data_dir()  # second call: old gone, new exists — no error

        assert new.exists()
        assert not old.exists()
