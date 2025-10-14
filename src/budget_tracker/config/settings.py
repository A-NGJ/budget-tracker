"""Application settings and configuration management."""

from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    config_dir: Path = Path.cwd() / "config"
    data_dir: Path = Path.cwd() / "data"
    output_dir: Path = Path.cwd() / "data" / "output"

    categories_file: Path = Path.cwd() / "config" / "categories.yaml"
    mappings_file: Path = Path.cwd() / "config" / "bank_mappings.json"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    default_output_filename: str = "standardized_transactions.csv"
    default_date_format: str = "%d-%m-%Y"  # DD-MM-YYYY format

    def load_categories(self) -> dict[str, Any]:
        """Load categories from YAML file."""
        with self.categories_file.open() as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
# settings = Settings()
@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    return settings
