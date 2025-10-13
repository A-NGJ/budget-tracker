from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.models.transaction import RawTransaction, StandardTransaction
from budget_tracker.normalizer.transformer import TransactionNormalizer


class BatchNormalizer:
    """Normalize batches of transactions"""

    def __init__(self) -> None:
        self.normalizer = TransactionNormalizer()

    def normalize_batch(
        self,
        raw_transactions: list[RawTransaction],
        mapping: BankMapping,
        categories: dict[str, str],  # Will come from LLM in next phase
    ) -> list[StandardTransaction]:
        """
        Normalize a batch of raw transactions.

        Args:
            raw_transactions: List of raw transactions
            mapping: Bank mapping configuration
            categories: Dict mapping transaction description to category

        Returns:
            List of successfully normalized transactions
        """
        normalized = []

        for raw in raw_transactions:
            # Get category from pre-categorized dict
            # In next phase, this will call LLM
            category = categories.get(
                raw.data.get(mapping.column_mapping.description_column, ""), "Other"
            )

            standard = self.normalizer.normalize(raw, mapping, category)
            if standard:
                normalized.append(standard)

        return normalized
