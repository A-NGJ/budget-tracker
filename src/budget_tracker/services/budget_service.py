"""BudgetService facade wrapping all core domain operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from budget_tracker.analytics.engine import AnalyticsEngine
from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.exporters import CSVExporter, ExcelExporter, GoogleSheetsExporter
from budget_tracker.filters import TransferDetector
from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.parsers.csv_parser import CSVParser
from budget_tracker.services.category_cache import CategoryCache

if TYPE_CHECKING:
    from datetime import date
    from decimal import Decimal
    from pathlib import Path

    import pandas as pd

    from budget_tracker.analytics.models import AnalyticsPeriod, AnalyticsResult
    from budget_tracker.config.settings import Settings
    from budget_tracker.filters.transfer_detector import TransferPair
    from budget_tracker.parsers.csv_parser import ParsedTransaction


class BudgetService:
    """Facade wrapping all core domain operations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._parser = CSVParser()
        self._transfer_detector = TransferDetector()
        self._currency_converter = CurrencyConverter()
        self._analytics_engine = AnalyticsEngine()
        self._category_cache = CategoryCache(settings)
        self._category_cache.load()

    # ── File operations ──────────────────────────────────────────────

    def detect_columns(self, file_path: Path) -> tuple[pd.DataFrame, list[str]]:
        """Parse CSV file and return DataFrame with detected columns."""
        return self._parser.parse_file(file_path)

    def parse_file(self, file_path: Path, mapping: BankMapping) -> list[ParsedTransaction]:
        """Load CSV using a bank mapping and extract parsed transactions."""
        return self._parser.load_with_mapping(file_path, mapping)

    # ── Bank mapping operations ──────────────────────────────────────

    def load_mapping(self, bank_name: str) -> BankMapping | None:
        """Load bank mapping from YAML file."""
        mapping_file = self._settings.banks_dir / f"{bank_name}.yaml"
        if not mapping_file.exists():
            return None
        with mapping_file.open() as f:
            data = yaml.safe_load(f)
        return BankMapping.model_validate(data)

    def save_mapping(self, mapping: BankMapping) -> None:
        """Save bank mapping to YAML file."""
        self._settings.banks_dir.mkdir(parents=True, exist_ok=True)
        mapping_file = self._settings.banks_dir / f"{mapping.bank_name}.yaml"
        with mapping_file.open("w") as f:
            yaml.safe_dump(mapping.model_dump(), f, default_flow_style=False, sort_keys=False)

    def list_mappings(self) -> list[str]:
        """Return sorted list of saved bank names."""
        if not self._settings.banks_dir.exists():
            return []
        return sorted(f.stem for f in self._settings.banks_dir.glob("*.yaml"))

    # ── Transfer operations ──────────────────────────────────────────

    def detect_transfers(
        self, transactions: list[ParsedTransaction]
    ) -> tuple[list[TransferPair], list[ParsedTransaction]]:
        """Detect internal transfer pairs from transactions."""
        return self._transfer_detector.detect(transactions)

    # ── Currency and transaction creation ────────────────────────────

    def convert_currency(
        self, amount: Decimal, from_currency: str, transaction_date: date
    ) -> Decimal:
        """Convert amount to DKK using historical exchange rates."""
        return self._currency_converter.convert(amount, from_currency, "DKK", transaction_date)

    def create_transaction(
        self,
        parsed: ParsedTransaction,
        category: str,
        subcategory: str | None,
        amount_dkk: Decimal,
    ) -> StandardTransaction:
        """Create a StandardTransaction from parsed data and categorization."""
        return StandardTransaction(
            date=parsed.date,
            category=category,
            subcategory=subcategory,
            amount=amount_dkk,
            source=parsed.source,
            description=parsed.description,
        )

    def create_transfer_transaction(self, parsed: ParsedTransaction) -> StandardTransaction:
        """Create a StandardTransaction for an internal transfer."""
        amount_dkk = self._currency_converter.convert(
            parsed.amount, parsed.currency, "DKK", parsed.date
        )
        return StandardTransaction(
            date=parsed.date,
            category="Internal Transfer",
            subcategory="Transfer",
            amount=amount_dkk,
            source=parsed.source,
            description=parsed.description,
        )

    # ── Category operations ──────────────────────────────────────────

    def load_categories(self) -> dict[str, list[str]]:
        """Load categories as dict mapping category name to subcategory list."""
        data = self._settings.load_categories()
        return {cat["name"]: cat.get("subcategories", []) for cat in data["categories"]}

    # ── Category cache ───────────────────────────────────────────────

    def get_cached_category(self, description: str) -> tuple[str, str | None] | None:
        """Look up cached category for a description."""
        return self._category_cache.get(description)

    def cache_category(self, description: str, category: str, subcategory: str | None) -> None:
        """Cache a category assignment for a description."""
        self._category_cache.set(description, category, subcategory)

    def save_cache(self) -> None:
        """Persist category cache to disk."""
        self._category_cache.save()

    def clear_cache(self) -> None:
        """Remove all cached category mappings."""
        self._category_cache.clear()

    # ── Analytics ────────────────────────────────────────────────────

    def compute_analytics(
        self, transactions: list[StandardTransaction], period: AnalyticsPeriod
    ) -> AnalyticsResult:
        """Compute analytics for transactions over a period."""
        return self._analytics_engine.compute(transactions, period)

    # ── Export ────────────────────────────────────────────────────────

    def export_excel(
        self,
        transactions: list[StandardTransaction],
        analytics: AnalyticsResult,
        output_path: Path | None = None,
    ) -> str:
        """Export transactions and analytics to Excel."""
        exporter = ExcelExporter(
            self._settings, analytics_result=analytics, output_file=output_path
        )
        return exporter.export(transactions)

    def export_csv(
        self,
        transactions: list[StandardTransaction],
        output_path: Path | None = None,
    ) -> str:
        """Export transactions to CSV."""
        exporter = CSVExporter(self._settings, output_file=output_path)
        return exporter.export(transactions)

    def export_google_sheets(
        self,
        transactions: list[StandardTransaction],
        analytics: AnalyticsResult,
    ) -> str:
        """Export transactions and analytics to Google Sheets."""
        exporter = GoogleSheetsExporter(self._settings, analytics_result=analytics)
        return exporter.export(transactions)

    # ── Blacklist operations ─────────────────────────────────────────

    def load_bank_blacklist(self, bank_name: str) -> list[str]:
        """Return blacklist keywords for a bank."""
        mapping = self.load_mapping(bank_name)
        if mapping is None:
            return []
        return mapping.blacklist_keywords

    def add_blacklist_keyword(self, bank_name: str, keyword: str) -> None:
        """Add a keyword to a bank's blacklist."""
        mapping = self.load_mapping(bank_name)
        if mapping is None:
            msg = f"No mapping found for bank '{bank_name}'"
            raise ValueError(msg)
        mapping.blacklist_keywords.append(keyword)
        self.save_mapping(mapping)

    def remove_blacklist_keyword(self, bank_name: str, keyword: str) -> None:
        """Remove a keyword from a bank's blacklist."""
        mapping = self.load_mapping(bank_name)
        if mapping is None:
            msg = f"No mapping found for bank '{bank_name}'"
            raise ValueError(msg)
        mapping.blacklist_keywords.remove(keyword)
        self.save_mapping(mapping)
