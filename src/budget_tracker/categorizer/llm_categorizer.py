import json

import ollama
import yaml
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from budget_tracker.config.settings import Settings, get_settings


class CategoryResult(BaseModel):
    """Result of LLM categorization"""

    category: str
    subcategory: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_confirmation: bool = False

    def __init__(
        self,
        category: str,
        confidence: float,
        subcategory: str | None = None,
        needs_confirmation: bool = False,
    ) -> None:
        super().__init__(
            category=category,
            subcategory=subcategory,
            confidence=confidence,
            needs_confirmation=needs_confirmation,
        )
        settings = get_settings()

        # Mark for confirmation if confidence is low
        if self.confidence < settings.ollama_confidence_threshold:
            self.needs_confirmation = True

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate that category exists in categories.yaml."""
        settings = get_settings()

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
        settings = get_settings()

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


class LLMCategorizer:
    """Categorize transactions using local LLM via Ollama"""

    def __init__(self, settings: Settings) -> None:
        self.categories = settings.load_categories()
        self.model = settings.ollama_model
        self.base_url = settings.ollama_base_url

    def categorize(self, description: str) -> CategoryResult:
        """
        Categorize a single transaction description.

        Args:
            description: Transaction description text

        Returns:
            CategoryResult with category, subcategory, and confidence
        """
        prompt = self._build_prompt(description)

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.1,  # Low temp for consistent categorization
                },
            )

            result = self._parse_response(response["response"])
            return result
        except Exception:
            # Fallback to Other category on error
            return CategoryResult(
                category="Other",
                subcategory="Uncategorized",
                confidence=0.0,
                needs_confirmation=True,
            )

    def categorize_batch(self, descriptions: list[str]) -> list[CategoryResult]:
        """Categorize multiple transactions"""
        return [self.categorize(desc) for desc in descriptions]

    def _build_prompt(self, description: str) -> str:
        """Build categorization prompt with context"""
        categories_text = self._format_categories()

        prompt = f"""You are a financial transaction categorizer. Analyze the \
transaction description and categorize it.

Available categories and subcategories:
{categories_text}

Transaction description: "{description}"

Respond with ONLY a JSON object in this exact format:
{{"category": "Category Name", "subcategory": "Subcategory Name", "confidence": 0.95}}

Confidence should be 0.0 to 1.0 where:
- 0.9-1.0: Very certain (e.g., "SPOTIFY.COM" -> Life & Entertainment/Streaming Services)
- 0.7-0.9: Confident (e.g., "Cafe Central" -> Food & Drinks/Coffee & Cafes)
- 0.4-0.7: Uncertain (e.g., "ABC123" -> needs user confirmation)
- 0.0-0.4: Very uncertain (use "Other/Uncategorized")

Choose the most specific subcategory possible. If description is unclear, use \
"Other/Uncategorized".

Some popular supermarkets:
- Netto
- Lidl
- Rema 1000
- Coop
- Føtex

They should be categorized as "Food & Drinks/Groceries"

Examples:

    User: Transaction description: "Andel Energi A/S"
    Assistant: {{"category": "Housing", "subcategory": "Electricity", "confidence": 0.95}}

    User: Transaction description: "Mieszkanie"
    Assistant: {{"category": "Housing", "subcategory": "Rent", "confidence": 0.90}}

    User: Transaction description: "Hellofresh Denmark"
    Assistant: {{"category": "Food & Drinks", "subcategory": "Groceries", "confidence": 0.92}}

    User: Transaction description: "Sygeforsikringen"
    Assistant: {{"category": "Health", "subcategory": "Health Insurance", "confidence": 0.88}}
"""
        return prompt

    def _format_categories(self) -> str:
        """Format categories for prompt"""
        lines = []
        for cat in self.categories["categories"]:
            lines.append(f"- {cat['name']}")
            for subcat in cat["subcategories"]:
                lines.append(f"  - {subcat}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> CategoryResult:
        """Parse LLM JSON response"""
        try:
            # Clean response (remove markdown code blocks if present)
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]

            data = json.loads(clean_response)
            return CategoryResult(**data)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback if parsing fails
            return CategoryResult(category="Other", subcategory="Uncategorized", confidence=0.0)
