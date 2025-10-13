from pathlib import Path

import pandas as pd

from budget_tracker.config.settings import settings
from budget_tracker.models.transaction import StandardTransaction


class CSVExporter:
    """Export standardized transactions to CSV"""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, transactions: list[StandardTransaction], output_file: Path) -> Path:
        """
        Export transactions to standardized CSV.

        Args:
            transactions: List of standardized transactions
            output_file: Output file path

        Returns:
            Path to created file
        """
        # Convert to DataFrame
        data = []
        for t in transactions:
            row = {
                "Date": t.date.strftime("%Y-%m-%d"),
                "Category": f"{t.category}" + (f"/{t.subcategory}" if t.subcategory else ""),
                "Amount (DKK)": float(t.amount),
                "Source": t.source,
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Sort by date
        df = df.sort_values("Date")

        # Ensure column order
        df = df[["Date", "Category", "Amount (DKK)", "Source"]]

        # Write to CSV
        df.to_csv(output_file, index=False)

        return output_file
