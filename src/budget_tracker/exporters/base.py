from typing import Protocol

from budget_tracker.models.transaction import StandardTransaction


class Exporter(Protocol):
    """Protocol for transaction exporters."""

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to the target destination

        Args:
            transactions: List of standardized transactions to export.

        Returns:
            String describing where the data was exported (file path or URL)
        """
        ...
