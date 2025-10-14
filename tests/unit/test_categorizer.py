from unittest.mock import patch

import pytest

from budget_tracker.categorizer.llm_categorizer import CategoryResult, LLMCategorizer


class TestLLMCategorizer:
    @pytest.fixture
    def categorizer(self) -> LLMCategorizer:
        return LLMCategorizer()

    @pytest.fixture
    def mock_ollama_response(self) -> dict[str, str]:
        return {
            "response": '{"category": "Food & Drinks", "subcategory": "Restaurants", "confidence": 0.95}'  # noqa: E501
        }

    def test_categorize_transaction(
        self, categorizer: LLMCategorizer, mock_ollama_response: dict[str, str]
    ) -> None:
        """Test categorizing a transaction description"""
        with patch("ollama.generate", return_value=mock_ollama_response):
            result = categorizer.categorize("Cafe Central - Copenhagen")
            assert result.category == "Food & Drinks"
            assert result.subcategory == "Restaurants"
            assert result.confidence == 0.95

    def test_low_confidence_detection(self, categorizer: LLMCategorizer) -> None:
        """Test detecting low confidence categorizations"""
        mock_response = {
            "response": '{"category": "Other", "subcategory": "Uncategorized", "confidence": 0.3}'
        }
        with patch("ollama.generate", return_value=mock_response):
            result = categorizer.categorize("XYZABC123")
            assert result.confidence < 0.5
            assert result.needs_confirmation is True

    def test_fallback_to_other_on_error(self, categorizer: LLMCategorizer) -> None:
        """Test falling back to Other category on LLM error"""
        with patch("ollama.generate", side_effect=Exception("Connection error")):
            result = categorizer.categorize("Some transaction")
            assert result.category == "Other"
            assert result.subcategory == "Uncategorized"

    def test_prompt_includes_category_list(self, categorizer: LLMCategorizer) -> None:
        """Test that prompt includes available categories"""
        with patch("ollama.generate") as mock_generate:
            mock_generate.return_value = {
                "response": '{"category": "Food & Drinks", "subcategory": "Restaurants", "confidence": 0.9}'  # noqa: E501
            }
            categorizer.categorize("Test transaction")
            # Verify prompt was constructed correctly
            call_args = mock_generate.call_args
            prompt = call_args[1]["prompt"]
            assert "Food & Drinks" in prompt
            assert "Transportation" in prompt

    def test_batch_categorization(self, categorizer: LLMCategorizer) -> None:
        """Test categorizing multiple transactions"""
        descriptions = ["Cafe Central", "Metro ticket", "Supermarket"]
        with patch("ollama.generate") as mock_generate:
            mock_generate.side_effect = [
                {
                    "response": '{"category": "Food & Drinks", "subcategory": "Restaurants", "confidence": 0.9}'  # noqa: E501
                },
                {
                    "response": '{"category": "Transportation", "subcategory": "Public Transport", "confidence": 0.95}'  # noqa: E501
                },
                {
                    "response": '{"category": "Food & Drinks", "subcategory": "Groceries", "confidence": 0.85}'  # noqa: E501
                },
            ]
            results = categorizer.categorize_batch(descriptions)
            assert len(results) == 3
            assert all(isinstance(r, CategoryResult) for r in results)
