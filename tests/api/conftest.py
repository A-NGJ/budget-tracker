"""Fixtures for the API test suite.

Builds an isolated ``BudgetService`` over a temp data directory, seeds it by
writing ``transactions.json`` directly (the store loads it via
``model_construct``, mirroring production and bypassing the category
validators), then injects it into a FastAPI app via ``dependency_overrides``.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from budget_tracker.api.app import create_app
from budget_tracker.api.dependencies import get_service
from budget_tracker.config.settings import Settings
from budget_tracker.services.budget_service import BudgetService

# Seed data written directly to the store's JSON file (store.load bypasses
# validators via model_construct, so categories need not exist in any yaml).
SEED_TRANSACTIONS: list[dict[str, str | None]] = [
    {
        "date": "2024-01-15",
        "category": "Food & Drinks",
        "subcategory": "Groceries",
        "amount": "-150.00",
        "source": "bank_a",
        "description": "NETTO GROCERY",
    },
    {
        "date": "2024-02-10",
        "category": "Food & Drinks",
        "subcategory": "Restaurants",
        "amount": "-300.00",
        "source": "bank_a",
        "description": "FANCY RESTAURANT",
    },
    {
        "date": "2024-01-20",
        "category": "Transportation",
        "subcategory": "Public Transport",
        "amount": "-50.00",
        "source": "bank_b",
        "description": "METRO CARD",
    },
    {
        "date": "2024-01-31",
        "category": "Income",
        "subcategory": "Salary",
        "amount": "5000.00",
        "source": "bank_a",
        "description": "MONTHLY SALARY",
    },
]


def _make_settings(tmp_path: Path) -> Settings:
    """Create isolated settings with a minimal categories file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    categories_file = config_dir / "categories.yaml"
    categories_file.write_text(
        yaml.safe_dump(
            {
                "categories": [
                    {"name": "Food & Drinks", "subcategories": ["Groceries", "Restaurants"]},
                    {"name": "Transportation", "subcategories": ["Public Transport"]},
                    {"name": "Income", "subcategories": ["Salary"]},
                    {"name": "Other"},
                ]
            }
        )
    )
    return Settings(
        config_dir=config_dir,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        banks_dir=tmp_path / "banks",
        categories_file=categories_file,
        default_categories_file=categories_file,
        category_mappings_file=tmp_path / "category_mappings.yaml",
        transactions_file=tmp_path / "transactions.json",
    )


@pytest.fixture
def seeded_service(tmp_path: Path) -> BudgetService:
    """A BudgetService whose store is preloaded with SEED_TRANSACTIONS."""
    settings = _make_settings(tmp_path)
    settings.transactions_file.parent.mkdir(parents=True, exist_ok=True)
    settings.transactions_file.write_text(json.dumps(SEED_TRANSACTIONS))
    return BudgetService(settings)


@pytest.fixture
def client(seeded_service: BudgetService) -> Iterator[TestClient]:
    """A TestClient whose get_service dependency returns the seeded service."""
    app = create_app()
    app.dependency_overrides[get_service] = lambda: seeded_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
