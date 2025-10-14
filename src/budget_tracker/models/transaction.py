"""Transaction data models for standardized transaction format."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StandardTransaction(BaseModel):
    """Standardized transaction format."""

    model_config = ConfigDict(frozen=False)  # Allow modifications for LLM categorization

    date: date
    category: str
    subcategory: str | None = None
    amount: Decimal
    source: str  # Bank name
    description: str | None = None  # Original description
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate that category is not empty."""
        # Will be validated against categories.yaml in later phase
        # For now, just ensure it's not empty
        if not v or not v.strip():
            msg = "Category cannot be empty"
            raise ValueError(msg)
        return v
