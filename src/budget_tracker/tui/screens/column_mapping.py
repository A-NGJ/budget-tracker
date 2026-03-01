"""Column mapping wizard screen for the budget tracker TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping

if TYPE_CHECKING:
    import pandas as pd
    from textual.app import ComposeResult
    from textual.binding import BindingType


STEP_TITLES = [
    "Bank Name",
    "Date Column",
    "Amount Column",
    "Description Columns",
    "Currency Config",
    "Date Format",
    "Decimal Separator",
    "Confirmation",
]

DATE_FORMAT_CHOICES = [
    ("DD-MM-YYYY (e.g., 31-12-2024)", "%d-%m-%Y"),
    ("YYYY-MM-DD (e.g., 2024-12-31)", "%Y-%m-%d"),
    ("MM/DD/YYYY (e.g., 12/31/2024)", "%m/%d/%Y"),
    ("DD/MM/YYYY (e.g., 31/12/2024)", "%d/%m/%Y"),
    ("YYYY/MM/DD (e.g., 2024/12/31)", "%Y/%m/%d"),
    ("DD.MM.YYYY (e.g., 31.12.2024)", "%d.%m.%Y"),
]

CURRENCY_CHOICES = [
    ("DKK (Danish Krone)", "DKK"),
    ("EUR (Euro)", "EUR"),
    ("USD (US Dollar)", "USD"),
    ("GBP (British Pound)", "GBP"),
    ("SEK (Swedish Krona)", "SEK"),
    ("NOK (Norwegian Krone)", "NOK"),
]


@dataclass
class MappingState:
    """Tracks collected values during mapping wizard."""

    bank_name: str | None = None
    date_col: str | None = None
    amount_col: str | None = None
    desc_cols: list[str] = field(default_factory=list)
    currency_col: str | None = None
    default_currency: str = "DKK"
    has_currency_column: bool = False
    date_format: str | None = None
    decimal_separator: str | None = None


class ColumnMappingScreen(ModalScreen[BankMapping | None]):
    """8-step column mapping wizard."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "go_back", "Back / Cancel"),
    ]

    DEFAULT_CSS = """
    ColumnMappingScreen {
        align: center middle;
    }
    #wizard-container {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #wizard-header {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #wizard-prompt {
        margin-bottom: 1;
    }
    #wizard-content {
        height: auto;
        max-height: 16;
    }
    #wizard-preview {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        columns: list[str],
        preview_data: pd.DataFrame,
        bank_name: str | None = None,
    ) -> None:
        super().__init__()
        self._columns = columns
        self._preview_data = preview_data
        self._state = MappingState(bank_name=bank_name)
        self._step_index = 0
        self._currency_substep = 0  # 0: has-column?, 1: select column or currency

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-container"):
            yield Static("", id="wizard-header")
            yield Static("", id="wizard-prompt")
            yield Vertical(id="wizard-content")
            yield Static("", id="wizard-preview")

    async def on_mount(self) -> None:
        await self._render_step()

    async def action_go_back(self) -> None:
        if self._step_index == 0:
            self.dismiss(None)
        elif self._step_index == 4 and self._currency_substep > 0:
            self._currency_substep = 0
            await self._render_step()
        else:
            if self._step_index == 3:
                self._state.desc_cols = []
            self._step_index -= 1
            await self._render_step()

    async def _render_step(self) -> None:
        """Clear and rebuild wizard content for current step."""
        header = self.query_one("#wizard-header", Static)
        prompt = self.query_one("#wizard-prompt", Static)
        content = self.query_one("#wizard-content", Vertical)
        preview = self.query_one("#wizard-preview", Static)

        title = STEP_TITLES[self._step_index]
        header.update(f"New Bank Mapping  (Step {self._step_index + 1}/8: {title})")
        preview.update("")
        await content.remove_children()

        match self._step_index:
            case 0:
                prompt.update("Enter bank name (e.g., 'Danske Bank', 'Nordea'):")
                input_widget = Input(
                    placeholder="Bank name...",
                    value=self._state.bank_name or "",
                    id="step-input",
                )
                await content.mount(input_widget)
                input_widget.focus()
            case 1:
                prompt.update("Which column contains the transaction date?")
                await self._mount_column_options(content)
            case 2:
                prompt.update("Which column contains the transaction amount?")
                await self._mount_column_options(content)
            case 3:
                await self._render_description_step(prompt, content)
            case 4:
                await self._render_currency_step(prompt, content)
            case 5:
                prompt.update("What date format does your file use?")
                options = [Option(label) for label, _ in DATE_FORMAT_CHOICES]
                options.append(Option("Other (custom format)"))
                option_list = OptionList(*options, id="step-options")
                await content.mount(option_list)
                option_list.focus()
            case 6:
                prompt.update("What character is used for decimal separation?")
                option_list = OptionList(
                    Option(". (dot/period) - e.g., 1234.56"),
                    Option(", (comma) - e.g., 1234,56"),
                    id="step-options",
                )
                await content.mount(option_list)
                option_list.focus()
            case 7:
                await self._render_confirmation(prompt, content)

    async def _mount_column_options(self, content: Vertical) -> None:
        """Mount OptionList with column names."""
        options = [Option(col) for col in self._columns]
        option_list = OptionList(*options, id="step-options")
        await content.mount(option_list)
        option_list.focus()

    async def _render_description_step(self, prompt: Static, content: Vertical) -> None:
        """Render description column multi-select."""
        if self._state.desc_cols:
            selected = " + ".join(self._state.desc_cols)
            prompt.update(f"Select description columns (selected: {selected}):")
        else:
            prompt.update("Which column(s) contain the description/text?")

        excluded = {self._state.date_col, self._state.amount_col, *self._state.desc_cols}
        remaining = [col for col in self._columns if col not in excluded]
        options = [Option(col) for col in remaining]
        if self._state.desc_cols:
            options.append(Option("Done selecting"))
        option_list = OptionList(*options, id="step-options")
        await content.mount(option_list)
        option_list.focus()

    async def _render_currency_step(self, prompt: Static, content: Vertical) -> None:
        """Render currency config step (two-part)."""
        if self._currency_substep == 0:
            prompt.update("Does the CSV have a currency column?")
            option_list = OptionList(
                Option("Yes - CSV has a currency column"),
                Option("No - use default currency"),
                id="step-options",
            )
            await content.mount(option_list)
            option_list.focus()
        elif self._state.has_currency_column:
            prompt.update("Which column contains the currency code?")
            await self._mount_column_options(content)
        else:
            prompt.update("Select default currency:")
            options = [Option(label) for label, _ in CURRENCY_CHOICES]
            options.append(Option("Other (enter custom)"))
            option_list = OptionList(*options, id="step-options")
            await content.mount(option_list)
            option_list.focus()

    async def _render_confirmation(self, prompt: Static, content: Vertical) -> None:
        """Render confirmation summary."""
        currency = self._state.currency_col or self._state.default_currency
        desc = " || ".join(self._state.desc_cols)
        summary = (
            f"  Bank: {self._state.bank_name}\n"
            f"  Date: {self._state.date_col} (format: {self._state.date_format})\n"
            f"  Amount: {self._state.amount_col}\n"
            f"  Description: {desc}\n"
            f"  Currency: {currency}\n"
            f"  Decimal separator: {self._state.decimal_separator}"
        )
        prompt.update("Review your mapping:")
        await content.mount(Static(summary, id="summary-text"))
        option_list = OptionList(
            Option("Yes - save this mapping"),
            Option("No - cancel"),
            id="step-options",
        )
        await content.mount(option_list)
        option_list.focus()

    def _get_column_preview(self, column: str) -> str:
        """Get preview values for a column."""
        if column not in self._preview_data.columns:
            return ""
        values = self._preview_data[column].dropna().head(3).tolist()
        if not values:
            return ""
        preview_lines = [f"  {v}" for v in values]
        return "Preview:\n" + "\n".join(preview_lines)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Update preview when highlighting column options."""
        if self._step_index in (1, 2, 3, 4) and event.option:
            col_name = str(event.option.prompt)
            if col_name in self._preview_data.columns:
                preview = self.query_one("#wizard-preview", Static)
                preview.update(self._get_column_preview(col_name))

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection to advance wizard."""
        selected = str(event.option.prompt)
        await self._handle_selection(selected)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission for text entry steps."""
        value = event.value.strip()
        if not value:
            self.notify("Please enter a value.", severity="warning")
            return

        if self._step_index == 0:
            self._state.bank_name = value
            await self._advance()
        elif self._step_index == 5:
            self._state.date_format = value
            await self._advance()
        elif (
            self._step_index == 4
            and self._currency_substep == 1
            and not self._state.has_currency_column
        ):
            self._state.default_currency = value
            self._currency_substep = 0
            await self._advance()

    async def _handle_selection(self, selected: str) -> None:
        """Route selection to appropriate step handler."""
        match self._step_index:
            case 1:
                self._state.date_col = selected
                await self._advance()
            case 2:
                self._state.amount_col = selected
                await self._advance()
            case 3:
                if selected == "Done selecting":
                    if not self._state.desc_cols:
                        self.notify(
                            "Select at least one description column.",
                            severity="warning",
                        )
                        return
                    await self._advance()
                else:
                    self._state.desc_cols.append(selected)
                    await self._render_step()
            case 4:
                await self._handle_currency_selection(selected)
            case 5:
                await self._handle_date_format_selection(selected)
            case 6:
                self._state.decimal_separator = "." if selected.startswith(".") else ","
                await self._advance()
            case 7:
                if selected.startswith("Yes"):
                    self.dismiss(self._build_mapping())
                else:
                    self.dismiss(None)

    async def _handle_currency_selection(self, selected: str) -> None:
        """Handle currency step selections."""
        if self._currency_substep == 0:
            self._state.has_currency_column = selected.startswith("Yes")
            self._currency_substep = 1
            await self._render_step()
        elif self._state.has_currency_column:
            self._state.currency_col = selected
            self._currency_substep = 0
            await self._advance()
        elif selected.startswith("Other"):
            content = self.query_one("#wizard-content", Vertical)
            prompt = self.query_one("#wizard-prompt", Static)
            await content.remove_children()
            prompt.update("Enter currency code (e.g., CHF, JPY):")
            input_widget = Input(
                placeholder="Currency code...",
                value=self._state.default_currency,
                id="step-input",
            )
            await content.mount(input_widget)
            input_widget.focus()
        else:
            for label, code in CURRENCY_CHOICES:
                if label == selected:
                    self._state.default_currency = code
                    break
            self._state.currency_col = None
            self._currency_substep = 0
            await self._advance()

    async def _handle_date_format_selection(self, selected: str) -> None:
        """Handle date format step selections."""
        if selected.startswith("Other"):
            content = self.query_one("#wizard-content", Vertical)
            prompt = self.query_one("#wizard-prompt", Static)
            await content.remove_children()
            prompt.update("Enter custom date format (e.g., %d.%m.%Y):")
            input_widget = Input(
                placeholder="Date format...",
                value=self._state.date_format or "%Y-%m-%d",
                id="step-input",
            )
            await content.mount(input_widget)
            input_widget.focus()
        else:
            for label, fmt in DATE_FORMAT_CHOICES:
                if label == selected:
                    self._state.date_format = fmt
                    break
            await self._advance()

    async def _advance(self) -> None:
        """Move to next step."""
        self._step_index += 1
        await self._render_step()

    def _build_mapping(self) -> BankMapping:
        """Build BankMapping from collected state."""
        return BankMapping(
            bank_name=self._state.bank_name or "",
            column_mapping=ColumnMapping(
                date_column=self._state.date_col or "",
                amount_column=self._state.amount_col or "",
                description_columns=self._state.desc_cols,
                currency_column=self._state.currency_col,
            ),
            date_format=self._state.date_format or "%Y-%m-%d",
            default_currency=self._state.default_currency,
            decimal_separator=self._state.decimal_separator or ".",
        )
