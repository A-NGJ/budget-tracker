from pathlib import Path

import pandas as pd

from budget_tracker.config.settings import Settings
from budget_tracker.models.transaction import StandardTransaction


class CSVExporter:
    """Export standardized transactions to CSV"""

    def __init__(self, settings: Settings, output_file: Path | None = None) -> None:
        self.output_dir = settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = output_file or (self.output_dir / settings.default_output_filename)

    def export(self, transactions: list[StandardTransaction]) -> str:
        """
        Export transactions to standardized CSV.

        Args:
            transactions: List of standardized transactions

        Returns:
            Path to created file as string
        """
        data = []
        for t in transactions:
            row = {
                "Transaction ID": t.transaction_id,
                "Date": t.date.strftime("%Y-%m-%d"),
                "Description": t.description,
                "Category": t.category,
                "Subcategory": t.subcategory,
                "Amount (DKK)": float(t.amount),
                "Source": t.source,
            }
            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("Date")
        df = df[
            [
                "Transaction ID",
                "Date",
                "Description",
                "Category",
                "Subcategory",
                "Amount (DKK)",
                "Source",
            ]
        ]
        df.to_csv(self.output_file, index=False)

        return str(self.output_file)
