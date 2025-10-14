"""Bank mapping models for CSV column configuration."""

from pydantic import BaseModel, ConfigDict


class ColumnMapping(BaseModel):
    """Maps CSV columns to standard fields."""

    date_column: str
    amount_column: str
    description_columns: list[str]  # One or more columns to combine with || separator
    currency_column: str | None = None  # Optional: if currency is in a column


class BankMapping(BaseModel):
    """Saved configuration for a specific bank's CSV format."""

    model_config = ConfigDict(frozen=False)

    bank_name: str
    column_mapping: ColumnMapping
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    default_currency: str = "DKK"  # Default currency if not specified per transaction
