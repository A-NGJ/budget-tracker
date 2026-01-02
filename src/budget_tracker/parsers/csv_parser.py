import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from budget_tracker.models.bank_mapping import BankMapping


class ParsedTransaction(BaseModel):
    """Parsed transaction with extracted and validated fields, before categorization."""

    date: date
    amount: Decimal  # In original currency
    currency: str
    description: str
    source: str  # Bank name
    source_file: str
    row_number: int | None = None


def detect_encoding(file_path: Path) -> str:
    """Detect file encoding by trying UTF-8 first, then ISO-8859-1"""
    for encoding in ["utf-8", "ISO-8859-1"]:
        try:
            with file_path.open(encoding=encoding) as f:
                f.read(1024)  # Try to read sample
                return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"  # Fallback default


def detect_delimiter(file_path: Path, encoding: str = "utf-8") -> str:
    """Detect CSV delimiter by analyzing first few lines"""
    with file_path.open(encoding=encoding) as f:
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
        encoding = detect_encoding(file_path)
        delimiter = detect_delimiter(file_path, encoding=encoding)

        try:
            df = pd.read_csv(file_path, delimiter=delimiter, dtype=str, encoding=encoding)
            # Strip whitespace from column names
            df.columns = df.columns.str.strip()
            return df, df.columns.tolist()
        except Exception as e:
            msg = f"Failed to parse CSV: {e}"
            raise ValueError(msg) from e

    def load_with_mapping(self, file_path: Path, mapping: BankMapping) -> list[ParsedTransaction]:
        """
        Load CSV using a pre-configured bank mapping and extract/parse all fields.

        Returns:
            List of ParsedTransaction objects with validated fields
        """
        df, _ = self.parse_file(file_path)

        transactions = []
        for idx, row in df.iterrows():
            # Skip rows with missing critical data
            date_str = row.get(mapping.column_mapping.date_column)
            amount_str = row.get(mapping.column_mapping.amount_column)

            if pd.isna(date_str) or pd.isna(amount_str):
                continue

            try:
                # Parse date
                parsed_date = self._parse_date(str(date_str), mapping.date_format)

                # Parse amount
                parsed_amount = self._parse_amount(str(amount_str), mapping.decimal_separator)

                # Determine currency
                if mapping.column_mapping.currency_column:
                    currency = str(
                        row.get(mapping.column_mapping.currency_column, mapping.default_currency)
                    )
                else:
                    currency = mapping.default_currency

                # Get description from one or more columns, combine with || separator
                description_parts = []
                for col in mapping.column_mapping.description_columns:
                    value = row.get(col)
                    if pd.isna(value):
                        continue
                    value = mapping.remove_blacklist_keywords(str(value))
                    if value:
                        description_parts.append(value)
                description = " || ".join(description_parts) if description_parts else ""

                transactions.append(
                    ParsedTransaction(
                        date=parsed_date,
                        amount=parsed_amount,
                        currency=currency.upper(),
                        description=description,
                        source=mapping.bank_name,
                        source_file=str(file_path),
                        row_number=int(idx) if isinstance(idx, (int, float)) else None,
                    )
                )
            except (ValueError, InvalidOperation) as e:
                # Skip malformed transactions
                print(f"Skipping invalid transaction in {file_path} at row {idx}: {e}")
                continue

        return transactions

    def _parse_date(self, date_str: str, date_format: str) -> date:
        """Parse date string according to format"""
        # ruff: noqa: DTZ007 - Bank statements contain dates without timezone info
        return datetime.strptime(date_str.strip(), date_format).date()

    def _parse_amount(self, amount_str: str, decimal_separator: str) -> Decimal:
        """Parse amount string handling different decimal separators"""
        # Remove whitespace and thousand separators
        clean_amount = amount_str.strip().replace(" ", "").replace("'", "")

        # Handle comma as decimal separator
        if decimal_separator == ",":
            clean_amount = clean_amount.replace(".", "").replace(",", ".")
        else:
            clean_amount = clean_amount.replace(",", "")

        return Decimal(clean_amount)
