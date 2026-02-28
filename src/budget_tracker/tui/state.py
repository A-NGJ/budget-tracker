"""PipelineState dataclass for shared pipeline data across TUI screens."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from budget_tracker.analytics.models import AnalyticsPeriod, AnalyticsResult
    from budget_tracker.filters.transfer_detector import TransferPair
    from budget_tracker.models.bank_mapping import BankMapping
    from budget_tracker.models.transaction import StandardTransaction
    from budget_tracker.parsers.csv_parser import ParsedTransaction


@dataclass
class PipelineState:
    """Shared state that flows through the processing pipeline."""

    # Input (set by FileSelectionScreen)
    files: list[Path] = field(default_factory=list)
    bank_names: list[str] = field(default_factory=list)
    mappings: dict[str, BankMapping] = field(default_factory=dict)

    # After parsing (set by FileSelectionScreen)
    parsed_transactions: list[ParsedTransaction] = field(default_factory=list)

    # After transfer detection (set by TransferReviewScreen)
    transfer_pairs: list[TransferPair] = field(default_factory=list)
    confirmed_transfers: list[TransferPair] = field(default_factory=list)
    rejected_transfers: list[TransferPair] = field(default_factory=list)
    transactions_to_categorize: list[ParsedTransaction] = field(default_factory=list)

    # After categorization (set by CategorizationScreen)
    categorized_transactions: list[StandardTransaction] = field(default_factory=list)

    # After period selection and analytics
    period: AnalyticsPeriod | None = None
    analytics: AnalyticsResult | None = None
