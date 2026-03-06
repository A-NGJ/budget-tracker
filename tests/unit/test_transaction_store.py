"""Unit tests for TransactionStore."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.services.transaction_store import TransactionStore

_TXN_DEFAULTS = {
    "date": date(2025, 10, 10),
    "category": "Food & Drinks",
    "subcategory": "Groceries",
    "amount": Decimal("-125.50"),
    "source": "Danske Bank",
    "description": "Cafe Central",
}


def _make_txn(
    overrides: dict[str, object] | None = None,
) -> StandardTransaction:
    """Create a transaction bypassing validators."""
    fields = {**_TXN_DEFAULTS, **(overrides or {})}
    return StandardTransaction.model_construct(**fields)  # type: ignore[arg-type]


class TestLoadAndSave:
    def test_load_empty_when_no_file(self, tmp_path: Path) -> None:
        store = TransactionStore(tmp_path / "transactions.json")
        store.load()
        assert store.count == 0

    def test_load_malformed_json_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "transactions.json"
        f.write_text('{"not": "a list"}')
        store = TransactionStore(f)
        store.load()
        assert store.count == 0

    def test_save_and_reload_roundtrip(self, tmp_path: Path) -> None:
        f = tmp_path / "transactions.json"
        store = TransactionStore(f)
        txn = _make_txn()
        store.add_many([txn])
        store.save()

        store2 = TransactionStore(f)
        store2.load()
        assert store2.count == 1
        loaded = store2.get_all()[0]
        assert loaded.date == txn.date
        assert loaded.amount == txn.amount
        assert loaded.source == txn.source
        assert loaded.category == txn.category
        assert loaded.subcategory == txn.subcategory
        assert loaded.description == txn.description

    def test_decimal_precision_preserved(self, tmp_path: Path) -> None:
        f = tmp_path / "transactions.json"
        store = TransactionStore(f)
        txn = _make_txn({"amount": Decimal("1234.56789")})
        store.add_many([txn])
        store.save()

        store2 = TransactionStore(f)
        store2.load()
        loaded = store2.get_all()[0]
        assert loaded.amount == Decimal("1234.56789")

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        f = tmp_path / "nested" / "deep" / "transactions.json"
        store = TransactionStore(f)
        store.add_many([_make_txn()])
        store.save()
        assert f.exists()

    def test_save_atomic_no_tmp_left(self, tmp_path: Path) -> None:
        f = tmp_path / "transactions.json"
        store = TransactionStore(f)
        store.add_many([_make_txn()])
        store.save()
        assert not f.with_suffix(".tmp").exists()


class TestAddMany:
    def test_add_returns_count_of_new(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        txns = [
            _make_txn({"description": "A"}),
            _make_txn({"description": "B"}),
        ]
        count = store.add_many(txns)
        assert count == 2
        assert store.count == 2

    def test_deduplication(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        txn = _make_txn()
        store.add_many([txn])
        count = store.add_many([txn])
        assert count == 0
        assert store.count == 1

    def test_deduplication_across_save_reload(self, tmp_path: Path) -> None:
        f = tmp_path / "transactions.json"
        store = TransactionStore(f)
        txn = _make_txn()
        store.add_many([txn])
        store.save()

        store2 = TransactionStore(f)
        store2.load()
        count = store2.add_many([txn])
        assert count == 0
        assert store2.count == 1


class TestGetAllAndCount:
    def test_get_all_returns_all(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        txns = [_make_txn({"description": "A"}), _make_txn({"description": "B"})]
        store.add_many(txns)
        assert len(store.get_all()) == 2

    def test_count(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        assert store.count == 0
        store.add_many([_make_txn()])
        assert store.count == 1


class TestGetSourcesAndCategories:
    def test_get_sources(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        store.add_many(
            [
                _make_txn({"source": "Danske Bank", "description": "A"}),
                _make_txn({"source": "Nordea", "description": "B"}),
                _make_txn({"source": "Danske Bank", "description": "C"}),
            ]
        )
        assert store.get_sources() == ["Danske Bank", "Nordea"]

    def test_get_categories(self) -> None:
        store = TransactionStore(Path("/dev/null"))
        store.add_many(
            [
                _make_txn({"category": "Food & Drinks", "description": "A"}),
                _make_txn({"category": "Transportation", "description": "B"}),
                _make_txn({"category": "Food & Drinks", "description": "C"}),
            ]
        )
        assert store.get_categories() == ["Food & Drinks", "Transportation"]


class TestGetFiltered:
    def _build_store(self) -> TransactionStore:
        store = TransactionStore(Path("/dev/null"))
        store.add_many(
            [
                _make_txn(
                    {
                        "date": date(2025, 1, 15),
                        "source": "Danske Bank",
                        "category": "Food & Drinks",
                        "subcategory": "Groceries",
                        "description": "txn1",
                    }
                ),
                _make_txn(
                    {
                        "date": date(2025, 2, 10),
                        "source": "Nordea",
                        "category": "Transportation",
                        "subcategory": "Public Transport",
                        "description": "txn2",
                    }
                ),
                _make_txn(
                    {
                        "date": date(2025, 3, 20),
                        "source": "Danske Bank",
                        "category": "Food & Drinks",
                        "subcategory": "Restaurants",
                        "description": "txn3",
                    }
                ),
            ]
        )
        return store

    def test_filter_by_source(self) -> None:
        store = self._build_store()
        result = store.get_filtered(source="Danske Bank")
        assert len(result) == 2

    def test_filter_by_category(self) -> None:
        store = self._build_store()
        result = store.get_filtered(category="Transportation")
        assert len(result) == 1
        assert result[0].description == "txn2"

    def test_filter_by_subcategory(self) -> None:
        store = self._build_store()
        result = store.get_filtered(subcategory="Restaurants")
        assert len(result) == 1
        assert result[0].description == "txn3"

    def test_filter_by_from_date(self) -> None:
        store = self._build_store()
        result = store.get_filtered(from_date=date(2025, 2, 1))
        assert len(result) == 2

    def test_filter_by_to_date(self) -> None:
        store = self._build_store()
        result = store.get_filtered(to_date=date(2025, 2, 28))
        assert len(result) == 2

    def test_filter_by_date_range(self) -> None:
        store = self._build_store()
        result = store.get_filtered(from_date=date(2025, 2, 1), to_date=date(2025, 2, 28))
        assert len(result) == 1
        assert result[0].description == "txn2"

    def test_filter_combined(self) -> None:
        store = self._build_store()
        result = store.get_filtered(source="Danske Bank", category="Food & Drinks")
        assert len(result) == 2

    def test_no_filters_returns_all(self) -> None:
        store = self._build_store()
        result = store.get_filtered()
        assert len(result) == 3
