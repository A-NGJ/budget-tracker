from pathlib import Path

from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.models.transaction import RawTransaction
from budget_tracker.parsers.csv_parser import CSVParser


class MultiFileProcessor:
    """Process multiple CSV files and combine results"""

    def __init__(self) -> None:
        self.parser = CSVParser()

    def process_files(
        self, file_paths: list[Path], mappings: dict[str, BankMapping]
    ) -> list[RawTransaction]:
        """
        Process multiple CSV files and return combined raw transactions.

        Args:
            file_paths: List of CSV files to process
            mappings: Dict of bank_name -> BankMapping

        Returns:
            Combined list of RawTransaction objects
        """
        all_transactions = []

        for file_path in file_paths:
            # Try to find matching mapping by filename or bank name
            mapping = self._find_mapping_for_file(file_path, mappings)

            if mapping:
                transactions = self.parser.load_with_mapping(file_path, mapping)
                all_transactions.extend(transactions)
            else:
                # Will need interactive mapping in CLI flow
                msg = f"No mapping found for {file_path.name}"
                raise ValueError(msg)

        return all_transactions

    def _find_mapping_for_file(
        self, file_path: Path, mappings: dict[str, BankMapping]
    ) -> BankMapping | None:
        """Try to match file to a saved bank mapping"""
        # Try exact match on filename stem
        for bank_name, mapping in mappings.items():
            if bank_name.lower() in file_path.stem.lower():
                return mapping
        return None
