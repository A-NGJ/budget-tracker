"""Transaction data models for standardized transaction format."""

from datetime import date
from decimal import Decimal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from budget_tracker.config.settings import settings


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
        """Validate that category exists in categories.yaml."""
        if not v or not v.strip():
            msg = "Category cannot be empty"
            raise ValueError(msg)

        if settings.categories_file.exists():
            data = yaml.safe_load(settings.categories_file.read_text())
            category_names = [cat["name"] for cat in data["categories"]]
            if v not in category_names:
                msg = f"Category '{v}' not found in categories.yaml"
                raise ValueError(msg)
        else:
            msg = f"Categories file not found: {settings.categories_file}"
            raise FileNotFoundError(msg)

        return v

    @field_validator("subcategory")
    @classmethod
    def validate_subcategory(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validate that subcategory exists in categories.yaml under the given category."""
        if v is None or not v.strip():
            return v

        category = info.data.get("category")
        if not category:
            msg = "Category must be set before validating subcategory"
            raise ValueError(msg)

        if settings.categories_file.exists():
            data = yaml.safe_load(settings.categories_file.read_text())
            for cat in data["categories"]:
                if cat["name"] == category:
                    subcategory_names = cat.get("subcategories", [])
                    if v not in subcategory_names:
                        msg = f"Subcategory '{v}' not found under category '{category}' in categories.yaml"  # noqa: E501
                        raise ValueError(msg)
                    return v
            msg = f"Category '{category}' not found in categories.yaml"
            raise ValueError(msg)
        else:
            msg = f"Categories file not found: {settings.categories_file}"
            raise FileNotFoundError(msg)

        return v
