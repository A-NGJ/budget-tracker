import json

import ollama
from pydantic import BaseModel, Field

from budget_tracker.config.settings import settings


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
        # Mark for confirmation if confidence is low
        if self.confidence < 0.6:
            self.needs_confirmation = True


class LLMCategorizer:
    """Categorize transactions using local LLM via Ollama"""

    def __init__(self) -> None:
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
        except (json.JSONDecodeError, KeyError):
            # Fallback if parsing fails
            return CategoryResult(category="Other", subcategory="Uncategorized", confidence=0.0)
