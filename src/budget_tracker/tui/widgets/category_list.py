"""CategoryList widget with subcategory drill-down."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList

if TYPE_CHECKING:
    from textual.app import ComposeResult


class CategoryList(Widget):
    """Category selector with subcategory drill-down."""

    class CategorySelected(Message):
        """Emitted when a final category (with optional subcategory) is selected."""

        def __init__(self, category: str, subcategory: str | None) -> None:
            super().__init__()
            self.category = category
            self.subcategory = subcategory

    class BackPressed(Message):
        """Emitted when '← Back' is selected in subcategory mode."""

    def __init__(self) -> None:
        super().__init__()
        self._categories: dict[str, list[str]] = {}
        self._category_names: list[str] = []
        self._subcategory_names: list[str] = []
        self._current_category: str | None = None

    def compose(self) -> ComposeResult:
        yield OptionList()

    def load_categories(self, categories: dict[str, list[str]]) -> None:
        """Load categories into the list."""
        self._categories = categories
        self._show_categories()

    def _show_categories(self) -> None:
        self._current_category = None
        self._category_names = list(self._categories.keys())
        opt_list = self.query_one(OptionList)
        opt_list.clear_options()
        for cat in self._category_names:
            opt_list.add_option(cat)
        if self._category_names:
            opt_list.highlighted = 0

    def _show_subcategories(self, category: str) -> None:
        self._current_category = category
        self._subcategory_names = list(self._categories[category])
        opt_list = self.query_one(OptionList)
        opt_list.clear_options()
        opt_list.add_option("← Back")
        for subcat in self._subcategory_names:
            opt_list.add_option(subcat)
        opt_list.highlighted = 0

    def is_in_subcategory_mode(self) -> bool:
        """Return True if currently showing subcategories."""
        return self._current_category is not None

    def back_to_categories(self) -> None:
        """Switch back to category view."""
        self._show_categories()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection for both category and subcategory modes."""
        idx = event.option_index
        if self._current_category is None:
            # Category mode
            if idx < 0 or idx >= len(self._category_names):
                return
            category = self._category_names[idx]
            if self._categories[category]:
                self._show_subcategories(category)
            else:
                self.post_message(CategoryList.CategorySelected(category, None))
        # Subcategory mode: index 0 is "← Back"
        elif idx == 0:
            self.back_to_categories()
            self.post_message(CategoryList.BackPressed())
        elif idx - 1 < len(self._subcategory_names):
            subcat = self._subcategory_names[idx - 1]
            self.post_message(CategoryList.CategorySelected(self._current_category, subcat))
