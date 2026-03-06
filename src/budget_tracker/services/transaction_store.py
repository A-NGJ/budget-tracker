"""Persistent transaction store with JSON backend."""

from __future__ import annotations

import json
from datetime import date as date_cls
from decimal import Decimal
from typing import TYPE_CHECKING

from budget_tracker.models.transaction import StandardTransaction

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path


class TransactionStore:
    """Manages persistent storage of categorized transactions.

    Follows CategoryCache pattern: load all into memory, work in-memory, save back to disk.
    Deduplicates transactions by transaction_id (SHA256 hash).
    """

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._transactions: dict[str, StandardTransaction] = {}

    def load(self) -> None:
        """Load transactions from JSON file into memory."""
        if not self._file_path.exists():
            return

        raw = json.loads(self._file_path.read_text())
        if not isinstance(raw, list):
            return

        for item in raw:
            # Use model_construct to bypass validators (categories may have changed)
            txn = StandardTransaction.model_construct(**item)
            # model_construct doesn't coerce types, so handle date/Decimal manually
            if isinstance(item.get("date"), str):
                object.__setattr__(txn, "date", date_cls.fromisoformat(item["date"]))
            if isinstance(item.get("amount"), (str, int, float)):
                object.__setattr__(txn, "amount", Decimal(str(item["amount"])))
            self._transactions[txn.transaction_id] = txn

    def save(self) -> None:
        """Persist transactions to disk with atomic write."""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        data = [txn.model_dump(mode="json") for txn in self._transactions.values()]
        tmp_path = self._file_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(self._file_path)

    def add_many(self, transactions: list[StandardTransaction]) -> int:
        """Add transactions, deduplicating by transaction_id. Returns count of new transactions."""
        count = 0
        for txn in transactions:
            tid = txn.transaction_id
            if tid not in self._transactions:
                self._transactions[tid] = txn
                count += 1
        return count

    def get_all(self) -> list[StandardTransaction]:
        """Return all stored transactions."""
        return list(self._transactions.values())

    def get_sources(self) -> list[str]:
        """Distinct source values, sorted."""
        return sorted({txn.source for txn in self._transactions.values()})

    def get_categories(self) -> list[str]:
        """Distinct category values, sorted."""
        return sorted({txn.category for txn in self._transactions.values()})

    def get_filtered(
        self,
        source: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[StandardTransaction]:
        """Return transactions matching all provided filters."""
        result = list(self._transactions.values())
        if source is not None:
            result = [t for t in result if t.source == source]
        if category is not None:
            result = [t for t in result if t.category == category]
        if subcategory is not None:
            result = [t for t in result if t.subcategory == subcategory]
        if from_date is not None:
            result = [t for t in result if t.date >= from_date]
        if to_date is not None:
            result = [t for t in result if t.date <= to_date]
        return result

    @property
    def count(self) -> int:
        """Number of stored transactions."""
        return len(self._transactions)
