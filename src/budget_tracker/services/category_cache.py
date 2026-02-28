"""Category mappings cache with YAML persistence."""

import yaml

from budget_tracker.config.settings import Settings


class CategoryCache:
    """Manages category mappings cache (YAML persistence)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache: dict[str, tuple[str, str | None]] = {}

    def load(self) -> None:
        """Load and validate cache from disk.

        Reads persisted category mappings from YAML and validates each entry
        against current categories.yaml. Invalid entries are silently skipped.
        """
        mappings_file = self._settings.category_mappings_file
        if not mappings_file.exists():
            return

        raw = yaml.safe_load(mappings_file.read_text())
        if not isinstance(raw, dict):
            return

        # Load valid categories for validation
        categories = self._settings.load_categories()
        valid_categories: dict[str, list[str]] = {}
        for cat in categories["categories"]:
            valid_categories[cat["name"]] = cat.get("subcategories", [])

        for description, mapping in raw.items():
            if not isinstance(mapping, dict):
                continue
            category = mapping.get("category")
            subcategory = mapping.get("subcategory")
            # Validate category exists
            if category not in valid_categories:
                continue
            # Validate subcategory if present
            if subcategory and subcategory not in valid_categories[category]:
                continue
            self._cache[str(description)] = (category, subcategory)

    def get(self, description: str) -> tuple[str, str | None] | None:
        """Look up cached category for a description."""
        return self._cache.get(description)

    def set(self, description: str, category: str, subcategory: str | None) -> None:
        """Cache a category assignment for a description."""
        self._cache[description] = (category, subcategory)

    def save(self) -> None:
        """Persist cache to disk as YAML."""
        mappings_file = self._settings.category_mappings_file
        mappings_file.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, dict[str, str | None]] = {}
        for description, (category, subcategory) in self._cache.items():
            data[description] = {"category": category, "subcategory": subcategory}

        mappings_file.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

    def clear(self) -> None:
        """Remove all cached mappings and delete the file."""
        self._cache.clear()
        mappings_file = self._settings.category_mappings_file
        if mappings_file.exists():
            mappings_file.unlink()
