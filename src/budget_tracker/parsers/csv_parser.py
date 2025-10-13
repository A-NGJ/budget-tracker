import csv
from pathlib import Path

import pandas as pd

from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.models.transaction import RawTransaction


def detect_delimiter(file_path: Path) -> str:
    """Detect CSV delimiter by analyzing first few lines"""
    with file_path.open(encoding="utf-8") as f:
        sample = f.read(1024)
        sniffer = csv.Sniffer()
        try:
            delimiter = sniffer.sniff(sample).delimiter
            return delimiter
        except csv.Error:
            return ","  # Default to comma


class CSVParser:
    """Parse bank statement CSV files"""

    def parse_file(self, file_path: Path) -> tuple[pd.DataFrame, list[str]]:
        """
        Parse CSV file and return DataFrame with detected columns.

        Returns:
            Tuple of (DataFrame, list of column names)
        """
        delimiter = detect_delimiter(file_path)
        try:
            df = pd.read_csv(file_path, delimiter=delimiter, dtype=str)
            # Strip whitespace from column names
            df.columns = df.columns.str.strip()
            return df, df.columns.tolist()
        except Exception as e:
            msg = f"Failed to parse CSV: {e}"
            raise ValueError(msg) from e

    def load_with_mapping(self, file_path: Path, mapping: BankMapping) -> list[RawTransaction]:
        """
        Load CSV using a pre-configured bank mapping.

        Returns:
            List of RawTransaction objects
        """
        df, _ = self.parse_file(file_path)

        transactions = []
        for idx, row in df.iterrows():
            # Skip rows with missing critical data
            if pd.isna(row.get(mapping.column_mapping.date_column)) or pd.isna(
                row.get(mapping.column_mapping.amount_column)
            ):
                continue

            transactions.append(
                RawTransaction(
                    data=row.to_dict(),
                    source_file=str(file_path),
                    row_number=int(idx) if isinstance(idx, (int, float)) else None,
                )
            )

        return transactions
