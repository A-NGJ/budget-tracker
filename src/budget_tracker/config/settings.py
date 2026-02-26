"""Application settings and configuration management."""

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_prefix="BUDGET_TRACKER_")

    config_dir: Path = Path.cwd() / "config"
    data_dir: Path = Path.cwd() / "data"
    output_dir: Path = Path.cwd() / "data" / "output"

    categories_file: Path = Path.cwd() / "config" / "categories.yaml"
    banks_dir: Path = Path.cwd() / "config" / "banks"

    default_output_filename: str = "standardized_transactions.xlsx"
    default_date_format: str = "%d-%m-%Y"  # DD-MM-YYYY format

    # Google Sheets settings
    google_credentials_dir: Path = Path.home() / ".budget-tracker"
    google_credentials_file: Path = Path.home() / ".budget-tracker" / "credentials.json"
    google_token_file: Path = Path.home() / ".budget-tracker" / "token.json"
    category_mappings_file: Path = Path.home() / ".budget-tracker" / "category_mappings.yaml"
    google_sheets_retry_attempts: int = 3
    google_sheets_retry_base_delay: float = 1.0  # seconds

    # CLI
    no_interactive: bool = False  # If True, disable interactive prompts

    def load_categories(self) -> dict[str, Any]:
        """Load categories from YAML file."""
        with self.categories_file.open() as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.banks_dir.mkdir(parents=True, exist_ok=True)


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    return settings
