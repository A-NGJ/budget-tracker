# Mapping Flow "Go Back" Navigation Implementation Plan

## Overview
Add "go back" functionality to the interactive column mapping flow (`mapping.py`), allowing users to return to previous prompts if they make a mistake. Adds a "← Go Back" menu option to selection menus, with previous selection memory.

## Current State Analysis

### Key Discoveries:
- `interactive_column_mapping()` at `mapping.py:13-199` is strictly sequential with no back navigation
- Uses `select_option()` from `selection.py:36-56` for arrow-key menus
- `select_option()` wraps `questionary.select()` for interactive terminals
- Blacklist CLI (`blacklist.py:83`) has simple "Back" to exit loops, but not step-by-step navigation
- The mapping flow has 7 distinct steps collecting values into local variables

### Current Flow Steps:
1. Bank name (text input) - line 28
2. Date column (select) - line 33
3. Amount column (select) - line 36
4. Description columns (multi-select loop) - lines 46-67
5. Currency config (y/n + select or text) - lines 74-113
6. Date format (select) - lines 116-154
7. Decimal separator (select) - lines 157-167

## Desired End State

Users can:
1. Select "← Go Back" from any selection menu to return to the previous step
2. See their previous selection pre-filled when going back
3. Navigate freely between steps before final confirmation

Verification:
- Run `budget-tracker process` with a new CSV file
- Navigate forward and backward through the mapping flow
- Confirm previous selections are remembered when going back

## What We're NOT Doing
- Adding back navigation to confirmation.py or transfer_confirmation.py (separate task)
- Adding back navigation to text input prompts (Rich.Prompt.ask) - only select menus
- Changing the blacklist.py flow (already has adequate navigation)

## Implementation Approach

Refactor the mapping flow from sequential variable assignment to a step-based state machine. Each step stores its result in a dictionary. The `select_option()` function gains an `allow_back` parameter that adds a "← Go Back" choice.

---

## Phase 1: Extend `select_option()` with Back Support

### Overview
Add `allow_back` parameter to `select_option()` that enables back navigation via menu option and keyboard shortcut.

### Changes Required:

#### 1. Update `select_option()` signature and logic
**File**: `src/budget_tracker/cli/selection.py`
**Changes**: Add `allow_back` parameter, return `None` when back is selected

```python
# Define a sentinel for "go back" action
BACK_SELECTED = object()


def select_option(
    message: str,
    choices: list[str],
    default: str | None = None,
    allow_back: bool = False,
) -> str | None:
    """Display an interactive selection menu.

    Uses questionary with arrow-key navigation on capable terminals,
    falls back to Rich Prompt on dumb terminals.

    Args:
        message: The prompt message to display
        choices: List of options to choose from
        default: Default selection (optional)
        allow_back: If True, adds "← Go Back" option to the choices

    Returns:
        The selected option string, or None if back was selected
    """
    if allow_back:
        choices = [*choices, "← Go Back"]

    if is_interactive_terminal(get_settings()):
        result = _questionary_select(message, choices, default, allow_back)
    else:
        result = _rich_select(message, choices, default)

    if result == "← Go Back":
        return None
    return result
```

The "← Go Back" option is added to the `choices` list by `select_option()` before calling either `_questionary_select()` or `_rich_select()`, so no changes are needed to those functions.

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`

#### Manual Verification:
- [x] Test `select_option()` with `allow_back=True` in a Python REPL
- [x] Verify "← Go Back" appears as last option and returns `None` when selected

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Refactor `interactive_column_mapping()` to Step-Based Flow

### Overview
Replace sequential prompts with a state machine that tracks current step index and collected values, enabling forward/backward navigation.

### Changes Required:

#### 1. Define step structure and state tracking
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add step definitions and refactor main function

```python
from dataclasses import dataclass, field
from enum import Enum, auto


class MappingStep(Enum):
    BANK_NAME = auto()
    DATE_COLUMN = auto()
    AMOUNT_COLUMN = auto()
    DESCRIPTION_COLUMNS = auto()
    CURRENCY_CONFIG = auto()
    DATE_FORMAT = auto()
    DECIMAL_SEPARATOR = auto()
    CONFIRM = auto()


class StepResult(Enum):
    NEXT = auto()
    BACK = auto()
    CANCEL = auto()
    DONE = auto()


@dataclass
class MappingState:
    """Tracks collected values during mapping flow."""
    bank_name: str | None = None
    date_col: str | None = None
    amount_col: str | None = None
    desc_cols: list[str] = field(default_factory=list)
    currency_col: str | None = None
    default_currency: str = "DKK"
    has_currency_column: bool = False
    date_format: str | None = None
    decimal_separator: str | None = None
```

#### 2. Refactor main function to step loop
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Replace sequential code with step-based loop

```python
def interactive_column_mapping(
    file_path: Path,
    columns: list[str],
    bank_name: str | None = None,
) -> BankMapping | None:
    """Guide user through interactive column mapping with back navigation."""
    console.print("\n[bold]Column Mapping Setup[/bold]")
    console.print(f"Available columns in CSV: {', '.join(columns)}\n")
    console.print("[dim]Tip: Select '← Go Back' to return to previous step[/dim]\n")

    state = MappingState(bank_name=bank_name)
    steps = list(MappingStep)
    step_idx = 0

    while step_idx < len(steps):
        current_step = steps[step_idx]
        allow_back = step_idx > 0  # Can't go back from first step

        result = _execute_step(current_step, state, columns, file_path, allow_back)

        match result:
            case StepResult.BACK:
                step_idx = max(0, step_idx - 1)
            case StepResult.CANCEL:
                return None
            case StepResult.DONE:
                return _build_mapping(state)
            case StepResult.NEXT:
                step_idx += 1

    return None
```

#### 3. Implement step execution functions
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add `_execute_step()` dispatcher and individual step handlers

```python
def _execute_step(
    step: MappingStep,
    state: MappingState,
    columns: list[str],
    file_path: Path,
    allow_back: bool,
) -> StepResult:
    """Execute a single step."""
    match step:
        case MappingStep.BANK_NAME:
            return _step_bank_name(state, file_path)
        case MappingStep.DATE_COLUMN:
            return _step_date_column(state, columns, allow_back)
        case MappingStep.AMOUNT_COLUMN:
            return _step_amount_column(state, columns, allow_back)
        case MappingStep.DESCRIPTION_COLUMNS:
            return _step_description_columns(state, columns, allow_back)
        case MappingStep.CURRENCY_CONFIG:
            return _step_currency_config(state, columns, allow_back)
        case MappingStep.DATE_FORMAT:
            return _step_date_format(state, allow_back)
        case MappingStep.DECIMAL_SEPARATOR:
            return _step_decimal_separator(state, allow_back)
        case MappingStep.CONFIRM:
            return _step_confirm(state, allow_back)
    return StepResult.NEXT


def _step_bank_name(state: MappingState, file_path: Path) -> StepResult:
    """Step 1: Bank name (no back from first step)."""
    state.bank_name = Prompt.ask(
        "Enter bank name (e.g., 'Danske Bank', 'Nordea')",
        default=state.bank_name or file_path.stem,
    )
    return StepResult.NEXT


def _step_date_column(state: MappingState, columns: list[str], allow_back: bool) -> StepResult:
    """Step 2: Date column selection."""
    result = select_option(
        "Which column contains the transaction date?",
        columns,
        default=state.date_col,
        allow_back=allow_back,
    )
    if result is None:
        return StepResult.BACK
    state.date_col = result
    return StepResult.NEXT


def _step_amount_column(state: MappingState, columns: list[str], allow_back: bool) -> StepResult:
    """Step 3: Amount column selection."""
    result = select_option(
        "Which column contains the transaction amount?",
        columns,
        default=state.amount_col,
        allow_back=allow_back,
    )
    if result is None:
        return StepResult.BACK
    state.amount_col = result
    return StepResult.NEXT


def _step_description_columns(
    state: MappingState, columns: list[str], allow_back: bool
) -> StepResult:
    """Step 4: Description column(s) selection."""
    console.print("\n[bold]Description Column(s)[/bold]")
    console.print("You can select one or more columns to combine into the description.")
    console.print(
        "Multiple columns will be joined with || separator "
        "(e.g., 'Text || Category || Subcategory')"
    )

    # Start fresh or continue from saved state
    desc_cols: list[str] = list(state.desc_cols) if state.desc_cols else []

    while True:
        remaining_cols = [
            col for col in columns
            if col not in desc_cols and col not in [state.date_col, state.amount_col]
        ]

        if not remaining_cols:
            console.print("[yellow]No more columns available to select.[/yellow]")
            break

        if desc_cols:
            console.print(f"\n[dim]Currently selected: {' + '.join(desc_cols)}[/dim]")
            add_more = Prompt.ask("Add another column?", choices=["y", "n"], default="n")
            if add_more == "n":
                break

        desc_col = select_option(
            "Which column contains description/text?" if not desc_cols else "Select another column",
            remaining_cols,
            allow_back=allow_back,
        )
        if desc_col is None:
            return StepResult.BACK
        desc_cols.append(desc_col)

    if not desc_cols:
        console.print("[red]Error: At least one description column is required[/red]")
        return StepResult.BACK  # Go back to try again

    state.desc_cols = desc_cols
    return StepResult.NEXT


def _step_currency_config(
    state: MappingState, columns: list[str], allow_back: bool
) -> StepResult:
    """Step 5: Currency configuration."""
    console.print("\n[bold]Currency Configuration[/bold]")

    has_currency_choices = ["Yes - CSV has a currency column", "No - use default currency"]
    default_currency_choice = has_currency_choices[0] if state.has_currency_column else has_currency_choices[1]

    has_currency_selection = select_option(
        "Does the CSV have a currency column?",
        has_currency_choices,
        default=default_currency_choice,
        allow_back=allow_back,
    )

    if has_currency_selection is None:
        return StepResult.BACK

    state.has_currency_column = has_currency_selection.startswith("Yes")

    if state.has_currency_column:
        result = select_option(
            "Which column contains the currency code?",
            columns,
            default=state.currency_col,
            allow_back=allow_back,
        )
        if result is None:
            return StepResult.BACK
        state.currency_col = result
    else:
        state.currency_col = None
        currency_choices = [
            "DKK (Danish Krone)",
            "EUR (Euro)",
            "USD (US Dollar)",
            "GBP (British Pound)",
            "SEK (Swedish Krona)",
            "NOK (Norwegian Krone)",
            "Other",
        ]

        # Find default based on saved state
        default_choice = None
        for choice in currency_choices:
            if choice.startswith(state.default_currency):
                default_choice = choice
                break

        currency_selection = select_option(
            "Select currency",
            currency_choices,
            default=default_choice or "DKK (Danish Krone)",
            allow_back=allow_back,
        )

        if currency_selection is None:
            return StepResult.BACK

        if currency_selection == "Other":
            state.default_currency = Prompt.ask(
                "Enter currency code (e.g., CHF, JPY)",
                default=state.default_currency,
            )
        else:
            state.default_currency = currency_selection.split()[0]

    return StepResult.NEXT


def _step_date_format(state: MappingState, allow_back: bool) -> StepResult:
    """Step 6: Date format selection."""
    console.print("\n[bold]Date Format Configuration[/bold]")

    date_format_choices = [
        "DD-MM-YYYY (e.g., 31-12-2024)",
        "YYYY-MM-DD (e.g., 2024-12-31)",
        "MM/DD/YYYY (e.g., 12/31/2024)",
        "DD/MM/YYYY (e.g., 31/12/2024)",
        "YYYY/MM/DD (e.g., 2024/12/31)",
        "DD.MM.YYYY (e.g., 31.12.2024)",
        "Other",
    ]
    date_format_map = {
        "DD-MM-YYYY (e.g., 31-12-2024)": "%d-%m-%Y",
        "YYYY-MM-DD (e.g., 2024-12-31)": "%Y-%m-%d",
        "MM/DD/YYYY (e.g., 12/31/2024)": "%m/%d/%Y",
        "DD/MM/YYYY (e.g., 31/12/2024)": "%d/%m/%Y",
        "YYYY/MM/DD (e.g., 2024/12/31)": "%Y/%m/%d",
        "DD.MM.YYYY (e.g., 31.12.2024)": "%d.%m.%Y",
    }

    # Find default choice based on saved state
    default_choice = None
    if state.date_format:
        for label, fmt in date_format_map.items():
            if fmt == state.date_format:
                default_choice = label
                break

    date_format_selection = select_option(
        "What date format does your file use?",
        date_format_choices,
        default=default_choice,
        allow_back=allow_back,
    )

    if date_format_selection is None:
        return StepResult.BACK

    if date_format_selection == "Other":
        console.print("\nEnter custom date format using Python strftime codes:")
        console.print("  %d = day, %m = month, %Y = year")
        console.print("  Example: '%d.%m.%Y' for 31.12.2024")
        state.date_format = Prompt.ask(
            "Enter date format",
            default=state.date_format or "%Y-%m-%d",
        )
    else:
        state.date_format = date_format_map[date_format_selection]

    return StepResult.NEXT


def _step_decimal_separator(state: MappingState, allow_back: bool) -> StepResult:
    """Step 7: Decimal separator selection."""
    console.print("\n[bold]Decimal Separator Configuration[/bold]")

    decimal_choices = [
        ". (dot/period) - e.g., 1234.56",
        ", (comma) - e.g., 1234,56",
    ]

    # Find default based on saved state
    default_choice = None
    if state.decimal_separator == ".":
        default_choice = decimal_choices[0]
    elif state.decimal_separator == ",":
        default_choice = decimal_choices[1]

    decimal_selection = select_option(
        "What character is used for decimal separation?",
        decimal_choices,
        default=default_choice or decimal_choices[0],
        allow_back=allow_back,
    )

    if decimal_selection is None:
        return StepResult.BACK

    state.decimal_separator = "." if decimal_selection.startswith(".") else ","
    return StepResult.NEXT


def _step_confirm(state: MappingState, allow_back: bool) -> StepResult:
    """Final confirmation step."""
    console.print("\n[bold green]Mapping created:[/bold green]")
    console.print(f"  Bank: {state.bank_name}")
    console.print(f"  Date: {state.date_col} (format: {state.date_format})")
    console.print(f"  Amount: {state.amount_col}")
    console.print(f"  Description: {' || '.join(state.desc_cols)}")
    console.print(f"  Currency: {state.currency_col or state.default_currency}")
    console.print(f"  Decimal separator: {state.decimal_separator}")

    save_choices = ["Yes - save this mapping", "No - cancel"]
    save_selection = select_option(
        "Save this mapping?",
        save_choices,
        default="Yes - save this mapping",
        allow_back=allow_back,
    )

    if save_selection is None:
        return StepResult.BACK
    if save_selection.startswith("Yes"):
        return StepResult.DONE
    return StepResult.CANCEL


def _build_mapping(state: MappingState) -> BankMapping:
    """Build BankMapping from collected state."""
    if state.bank_name is None:
        raise ValueError("bank_name is required")
    if state.date_col is None:
        raise ValueError("date_col is required")
    if state.amount_col is None:
        raise ValueError("amount_col is required")
    if not state.desc_cols:
        raise ValueError("desc_cols is required")
    if state.date_format is None:
        raise ValueError("date_format is required")
    if state.decimal_separator is None:
        raise ValueError("decimal_separator is required")

    return BankMapping(
        bank_name=state.bank_name,
        column_mapping=ColumnMapping(
            date_column=state.date_col,
            amount_column=state.amount_col,
            description_columns=state.desc_cols,
            currency_column=state.currency_col,
        ),
        date_format=state.date_format,
        default_currency=state.default_currency,
        decimal_separator=state.decimal_separator,
    )
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`

#### Manual Verification:
- [ ] Run `budget-tracker process` with a new bank CSV
- [ ] Navigate through all steps, go back at each step
- [ ] Verify previous selections are remembered
- [ ] Confirm final mapping saves correctly

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 3: Add Tests

### Overview
Add unit tests for the back navigation in `select_option()` and the refactored mapping flow.

### Current Test State
- **test_selection.py**: Has tests for `select_option()` but not the `allow_back` parameter
- **test_mapping.py**: Minimal tests focused on YAML save/load - no tests for step-based navigation
- **Mocking pattern**: Uses `@patch` decorators with `MagicMock`
- **Test style**: Class-based grouping (`Test*` classes)

### Changes Required:

#### 1. Update selection tests
**File**: `tests/unit/test_selection.py`
**Changes**: Add `TestSelectOptionWithBackNavigation` class

```python
class TestSelectOptionWithBackNavigation:
    """Tests for allow_back parameter in select_option."""

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_allow_back_adds_go_back_option_to_choices(
        self,
        mock_rich: MagicMock,
        mock_is_interactive: MagicMock,
    ) -> None:
        """Verify '← Go Back' is appended to choices when allow_back=True."""
        mock_rich.return_value = "Option 1"

        select_option("Choose:", ["Option 1", "Option 2"], allow_back=True)

        # Check that "← Go Back" was added to the choices
        call_args = mock_rich.call_args[0]
        assert call_args[1] == ["Option 1", "Option 2", "← Go Back"]

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_selecting_go_back_returns_none(
        self,
        mock_rich: MagicMock,
        mock_is_interactive: MagicMock,
    ) -> None:
        """Verify selecting '← Go Back' returns None."""
        mock_rich.return_value = "← Go Back"

        result = select_option("Choose:", ["Option 1", "Option 2"], allow_back=True)

        assert result is None

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_selecting_regular_option_returns_value(
        self,
        mock_rich: MagicMock,
        mock_is_interactive: MagicMock,
    ) -> None:
        """Verify selecting a regular option still returns that option."""
        mock_rich.return_value = "Option 2"

        result = select_option("Choose:", ["Option 1", "Option 2"], allow_back=True)

        assert result == "Option 2"

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_allow_back_false_does_not_add_option(
        self,
        mock_rich: MagicMock,
        mock_is_interactive: MagicMock,
    ) -> None:
        """Verify allow_back=False (default) doesn't add Go Back option."""
        mock_rich.return_value = "Option 1"

        select_option("Choose:", ["Option 1", "Option 2"], allow_back=False)

        call_args = mock_rich.call_args[0]
        assert "← Go Back" not in call_args[1]
```

#### 2. Add mapping flow tests
**File**: `tests/unit/test_mapping.py`
**Changes**: Add fixtures and test classes for MappingState, step functions, navigation flow, and _build_mapping

##### Fixtures to Add:

```python
@pytest.fixture
def sample_columns() -> list[str]:
    """Standard column list for testing."""
    return ["Date", "Amount", "Description", "Category", "Currency"]


@pytest.fixture
def complete_state() -> MappingState:
    """Fully populated MappingState for testing."""
    return MappingState(
        bank_name="Test Bank",
        date_col="Date",
        amount_col="Amount",
        desc_cols=["Description"],
        currency_col=None,
        default_currency="DKK",
        date_format="%Y-%m-%d",
        decimal_separator=".",
    )
```

##### Test Classes:

```python
class TestMappingState:
    """Test MappingState dataclass initialization and defaults."""

    def test_initializes_with_none_values(self) -> None:
        """Verify MappingState fields initialize to expected defaults."""
        state = MappingState()

        assert state.bank_name is None
        assert state.date_col is None
        assert state.amount_col is None
        assert state.desc_cols == []
        assert state.currency_col is None
        assert state.default_currency == "DKK"
        assert state.has_currency_column is False
        assert state.date_format is None
        assert state.decimal_separator is None

    def test_desc_cols_uses_independent_list(self) -> None:
        """Verify each MappingState instance has its own desc_cols list."""
        state1 = MappingState()
        state2 = MappingState()

        state1.desc_cols.append("Description")

        assert state2.desc_cols == []  # Should not be affected

    def test_accepts_initial_values(self) -> None:
        """Verify MappingState accepts initial values."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            default_currency="EUR",
        )

        assert state.bank_name == "Test Bank"
        assert state.date_col == "Date"
        assert state.default_currency == "EUR"


class TestStepDateColumn:
    """Tests for _step_date_column."""

    @patch("budget_tracker.cli.mapping.select_option")
    def test_returns_back_when_none_selected(
        self, mock_select: MagicMock
    ) -> None:
        """Verify BACK is returned when select_option returns None."""
        mock_select.return_value = None
        state = MappingState()

        result = _step_date_column(state, ["Date", "Amount"], allow_back=True)

        assert result == StepResult.BACK
        assert state.date_col is None  # State unchanged

    @patch("budget_tracker.cli.mapping.select_option")
    def test_stores_selection_and_returns_next(
        self, mock_select: MagicMock
    ) -> None:
        """Verify selection is stored and NEXT is returned."""
        mock_select.return_value = "Date"
        state = MappingState()

        result = _step_date_column(state, ["Date", "Amount"], allow_back=True)

        assert result == StepResult.NEXT
        assert state.date_col == "Date"

    @patch("budget_tracker.cli.mapping.select_option")
    def test_passes_previous_selection_as_default(
        self, mock_select: MagicMock
    ) -> None:
        """Verify previous selection is passed as default when going back."""
        mock_select.return_value = "Date"
        state = MappingState(date_col="Amount")  # Previous selection

        _step_date_column(state, ["Date", "Amount"], allow_back=True)

        # Verify default was passed
        call_kwargs = mock_select.call_args
        assert call_kwargs[1]["default"] == "Amount"


class TestInteractiveColumnMappingNavigation:
    """Tests for step-based navigation in interactive_column_mapping."""

    @pytest.fixture
    def sample_columns(self) -> list[str]:
        return ["Date", "Amount", "Description", "Currency"]

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping._build_mapping")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_forward_navigation_increments_step(
        self,
        mock_print: MagicMock,
        mock_build: MagicMock,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify NEXT result moves to next step."""
        mock_execute.side_effect = [
            StepResult.NEXT,
            StepResult.NEXT,
            StepResult.DONE,
        ]
        mock_build.return_value = MagicMock()

        interactive_column_mapping(sample_columns)

        # Should have called execute 3 times for steps 0, 1, 2
        assert mock_execute.call_count == 3

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_back_navigation_decrements_step(
        self,
        mock_print: MagicMock,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify BACK result moves to previous step."""
        mock_execute.side_effect = [
            StepResult.NEXT,  # Step 0 → 1
            StepResult.NEXT,  # Step 1 → 2
            StepResult.BACK,  # Step 2 → 1
            StepResult.CANCEL,  # Exit
        ]

        interactive_column_mapping(sample_columns)

        # Step 1 should be called twice (forward and after back)
        assert mock_execute.call_count == 4

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_back_from_first_step_stays_at_first(
        self,
        mock_print: MagicMock,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify BACK from step 0 stays at step 0."""
        mock_execute.side_effect = [
            StepResult.BACK,  # Can't go back, stays at 0
            StepResult.CANCEL,  # Exit
        ]

        interactive_column_mapping(sample_columns)

        # First step should be called twice
        assert mock_execute.call_count == 2
        # Both calls should be for step index 0 (MappingStep.BANK_NAME)
        first_call_step = mock_execute.call_args_list[0][0][0]
        second_call_step = mock_execute.call_args_list[1][0][0]
        assert first_call_step == MappingStep.BANK_NAME
        assert second_call_step == MappingStep.BANK_NAME

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_cancel_returns_none(
        self,
        mock_print: MagicMock,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify CANCEL result returns None from flow."""
        mock_execute.return_value = StepResult.CANCEL

        result = interactive_column_mapping(sample_columns)

        assert result is None


class TestBuildMapping:
    """Tests for _build_mapping validation."""

    def test_raises_on_missing_bank_name(self) -> None:
        """Verify ValueError raised when bank_name is None."""
        state = MappingState(
            date_col="Date",
            amount_col="Amount",
            desc_cols=["Description"],
            date_format="%Y-%m-%d",
            decimal_separator=".",
        )

        with pytest.raises(ValueError, match="bank_name is required"):
            _build_mapping(state)

    def test_raises_on_empty_desc_cols(self) -> None:
        """Verify ValueError raised when desc_cols is empty."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            amount_col="Amount",
            desc_cols=[],  # Empty!
            date_format="%Y-%m-%d",
            decimal_separator=".",
        )

        with pytest.raises(ValueError, match="desc_cols is required"):
            _build_mapping(state)

    def test_builds_valid_mapping(self) -> None:
        """Verify valid state produces correct BankMapping."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            amount_col="Amount",
            desc_cols=["Description", "Category"],
            currency_col="Currency",
            default_currency="EUR",
            date_format="%d-%m-%Y",
            decimal_separator=",",
        )

        result = _build_mapping(state)

        assert result.bank_name == "Test Bank"
        assert result.column_mapping.date_column == "Date"
        assert result.column_mapping.description_columns == ["Description", "Category"]
        assert result.default_currency == "EUR"
        assert result.decimal_separator == ","
```

### Implementation Order

1. **Add selection tests first** - Quick wins, validates `allow_back` parameter
2. **Add MappingState tests** - Validates dataclass behavior
3. **Add _build_mapping tests** - Validates final output
4. **Add step function tests** - One representative step (date_column)
5. **Add navigation flow tests** - Integration of step loop

### Success Criteria:

#### Automated Verification:
- [x] All tests pass: `pytest tests/unit/test_selection.py tests/unit/test_mapping.py -v`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

---

## Testing Strategy

### Unit Tests:
- `select_option()` with `allow_back=True` adds "← Go Back" option
- `select_option()` returns `None` when back is selected
- `MappingState` correctly tracks and preserves values
- Each `_step_*` function returns `StepResult.BACK` when back is selected
- Step index decrements correctly on back navigation

### Manual Testing:
1. Run `budget-tracker process some_new_bank.csv`
2. Go through mapping, intentionally select wrong column
3. Select "← Go Back" from menu, verify previous step shown with previous selection
4. Complete mapping, verify final result is correct
5. Test in non-interactive mode (BUDGET_TRACKER_NO_INTERACTIVE=1)

## References
- Current implementation: `src/budget_tracker/cli/mapping.py:13-199`
- Selection utility: `src/budget_tracker/cli/selection.py:36-56`
- Blacklist back pattern: `src/budget_tracker/cli/blacklist.py:83-84`
- Arrow-key plan: `.claude/thoughts/shared/plans/2026-01-17-interactive-arrow-key-selection.md`
