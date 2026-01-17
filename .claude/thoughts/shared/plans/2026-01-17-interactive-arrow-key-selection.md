# Interactive Arrow-Key Selection Implementation Plan

## Overview
Add arrow-key selection using questionary to the blacklist CLI, while preserving number-typing support and gracefully falling back to Rich prompts on dumb terminals.

## Current State Analysis
- All menus use `rich.prompt.Prompt.ask()` with numbered choices (`blacklist.py:91`, `confirmation.py:74-77`)
- No arrow-key libraries installed - only `typer[all]` and `rich>=13.7.0`
- Blacklist CLI has two menus: bank selection (`blacklist.py:117-122`) and action selection (`blacklist.py:86-91`)

### Key Discoveries:
- `questionary.select()` supports `use_shortcuts=True` for number typing alongside arrows
- Dumb terminals (`TERM=dumb`) cause issues with prompt_toolkit (questionary's backend)
- Current pattern: display list → `Prompt.ask()` with choices → match on result

## Desired End State
- User can navigate menus with arrow keys (Up/Down) and press Enter to select
- User can still type numbers to select options directly
- On dumb terminals (CI, Emacs shell, etc.), falls back to existing Rich prompt behavior
- Blacklist management CLI (`budget-tracker blacklist`) uses the new selection

## What We're NOT Doing
- Updating other CLI modules (confirmation.py, mapping.py) - future work
- Adding questionary to all interactive prompts - only menus with numbered choices
- Custom styling/theming for questionary - use defaults

## Implementation Approach
Create a `selection.py` utility module that abstracts the choice between questionary and Rich prompts based on terminal capabilities. Update blacklist.py to use this utility.

---

## Phase 1: Add questionary Dependency

### Overview
Add questionary to project dependencies.

### Changes Required:

#### 1. Update pyproject.toml
**File**: `pyproject.toml`
**Changes**: Add questionary to dependencies list

```toml
dependencies = [
    "typer[all]>=0.12.0",
    "pandas>=2.2.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.3.0",
    "ollama>=0.3.0",
    "pyyaml>=6.0.1",
    "rich>=13.7.0",
    "httpx>=0.27.0",
    "gspread>=6.2.1",
    "questionary>=2.0.0",
]
```

### Success Criteria:

#### Automated Verification:
- [x] `uv sync` completes successfully
- [x] `python -c "import questionary; print(questionary.__version__)"` works

---

## Phase 2: Create Selection Utility Module

### Overview
Create a utility module that provides interactive selection with terminal detection and fallback.

### Changes Required:

#### 1. New Selection Utility Module
**File**: `src/budget_tracker/cli/selection.py`
**Changes**: Create new file

```python
"""Interactive selection utilities with arrow-key support and fallback."""

import os
import sys

from rich.console import Console
from rich.prompt import Prompt

console = Console()


def is_interactive_terminal() -> bool:
    """Check if the terminal supports interactive arrow-key selection.

    Returns False for:
    - Dumb terminals (TERM=dumb or TERM=unknown)
    - Non-TTY environments (piped input/output)
    - Explicitly disabled via BUDGET_TRACKER_NO_INTERACTIVE env var
    """
    # Check for explicit disable
    if os.environ.get("BUDGET_TRACKER_NO_INTERACTIVE"):
        return False

    # Check if stdin/stdout are TTYs
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    # Check for dumb terminal
    term = os.environ.get("TERM", "").lower()
    if term in ("dumb", "unknown", ""):
        return False

    return True


def select_option(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """Display an interactive selection menu.

    Uses questionary with arrow-key navigation on capable terminals,
    falls back to Rich Prompt on dumb terminals.

    Args:
        message: The prompt message to display
        choices: List of options to choose from
        default: Default selection (optional)

    Returns:
        The selected option string
    """
    if is_interactive_terminal():
        return _questionary_select(message, choices, default)
    else:
        return _rich_select(message, choices, default)


def _questionary_select(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """Arrow-key selection using questionary."""
    import questionary

    result = questionary.select(
        message,
        choices=choices,
        default=default,
        use_shortcuts=True,  # Enable number keys alongside arrows
        use_arrow_keys=True,
        use_jk_keys=True,  # vim-style navigation
    ).ask()

    # Handle Ctrl+C (returns None)
    if result is None:
        raise KeyboardInterrupt

    return result


def _rich_select(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """Numbered selection fallback using Rich."""
    # Display numbered options
    console.print(f"\n[bold]{message}[/bold]")
    for i, choice in enumerate(choices, 1):
        console.print(f"  {i}. {choice}")

    # Build choices list (numbers as strings)
    num_choices = [str(i) for i in range(1, len(choices) + 1)]

    # Determine default number
    default_num = None
    if default and default in choices:
        default_num = str(choices.index(default) + 1)

    choice_num = Prompt.ask(
        "Select",
        choices=num_choices,
        default=default_num,
    )

    return choices[int(choice_num) - 1]
```

#### 2. Unit Tests for Selection Module
**File**: `tests/unit/test_selection.py`
**Changes**: Create new test file

```python
"""Tests for interactive selection utilities."""

import os
from unittest.mock import patch, MagicMock

import pytest

from budget_tracker.cli.selection import (
    is_interactive_terminal,
    select_option,
    _rich_select,
)


class TestIsInteractiveTerminal:
    """Tests for terminal detection."""

    def test_returns_false_when_env_var_set(self):
        """Explicit disable via environment variable."""
        with patch.dict(os.environ, {"BUDGET_TRACKER_NO_INTERACTIVE": "1"}):
            assert is_interactive_terminal() is False

    def test_returns_false_when_stdin_not_tty(self):
        """Non-TTY stdin (e.g., piped input)."""
        with patch("sys.stdin.isatty", return_value=False):
            assert is_interactive_terminal() is False

    def test_returns_false_when_stdout_not_tty(self):
        """Non-TTY stdout (e.g., piped output)."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=False):
                assert is_interactive_terminal() is False

    def test_returns_false_for_dumb_terminal(self):
        """Dumb terminal should use fallback."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                with patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
                    assert is_interactive_terminal() is False

    def test_returns_false_for_unknown_terminal(self):
        """Unknown terminal should use fallback."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                with patch.dict(os.environ, {"TERM": "unknown"}, clear=False):
                    assert is_interactive_terminal() is False

    def test_returns_true_for_xterm(self):
        """Standard xterm should be interactive."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=False):
                    assert is_interactive_terminal() is True


class TestSelectOption:
    """Tests for select_option function."""

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_uses_rich_fallback_on_dumb_terminal(self, mock_rich, mock_is_interactive):
        """Should use Rich when terminal is not interactive."""
        mock_rich.return_value = "Option 1"

        result = select_option("Choose:", ["Option 1", "Option 2"])

        mock_rich.assert_called_once_with("Choose:", ["Option 1", "Option 2"], None)
        assert result == "Option 1"

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=True)
    @patch("budget_tracker.cli.selection._questionary_select")
    def test_uses_questionary_on_interactive_terminal(self, mock_quest, mock_is_interactive):
        """Should use questionary when terminal is interactive."""
        mock_quest.return_value = "Option 2"

        result = select_option("Choose:", ["Option 1", "Option 2"], default="Option 2")

        mock_quest.assert_called_once_with("Choose:", ["Option 1", "Option 2"], "Option 2")
        assert result == "Option 2"


class TestRichSelect:
    """Tests for Rich fallback selection."""

    @patch("budget_tracker.cli.selection.Prompt.ask")
    def test_returns_selected_choice(self, mock_prompt):
        """Should return the choice corresponding to selected number."""
        mock_prompt.return_value = "2"

        result = _rich_select("Pick one:", ["Apple", "Banana", "Cherry"])

        assert result == "Banana"

    @patch("budget_tracker.cli.selection.Prompt.ask")
    def test_passes_default_as_number(self, mock_prompt):
        """Should convert default choice to its number."""
        mock_prompt.return_value = "2"

        _rich_select("Pick one:", ["Apple", "Banana", "Cherry"], default="Banana")

        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args[1]
        assert call_kwargs["default"] == "2"  # Banana is index 1, so number 2
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`
- [x] Tests pass: `pytest tests/unit/test_selection.py -v`

#### Manual Verification:
- [ ] Module imports without error: `python -c "from budget_tracker.cli.selection import select_option"`

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 3: Update Blacklist CLI

### Overview
Replace Prompt.ask() menu calls in blacklist.py with the new select_option utility.

### Changes Required:

#### 1. Update Blacklist Module
**File**: `src/budget_tracker/cli/blacklist.py`
**Changes**: Import and use select_option for menu selections

**Add import** (after line 5):
```python
from budget_tracker.cli.selection import select_option
```

**Replace bank selection** (lines 116-122):
```python
# Before:
console.print("\n[bold]Abailable banks:[/bold]")
for i, b in enumerate(banks, start=1):
    console.print(f"    {i}. {b}")
console.print(f"    {len(banks) + 1}. Exit")

choices = [str(i) for i in range(1, len(banks) + 2)]
choice = Prompt.ask("Select bank", choices=choices, default=str(len(banks) + 1))

# After:
bank_choices = [*banks, "Exit"]
selected = select_option("Select bank", bank_choices, default="Exit")

if selected == "Exit":
    console.print("[dim]Exiting blacklist management[/dim]")
    break

bank_name = selected
```

**Replace action selection** (lines 84-91):
```python
# Before:
console.print("\n[bold]Select action:[/bold]")
console.print(" 1. Add keyword")
console.print(" 2. Remove keyword")
console.print(" 3. Back")

choice = Prompt.ask("Enter choice", choices=["1", "2", "3"], default="3")

match choice:
    case "1":
        add_keyword(mapping, banks_dir)
    case "2":
        remove_keyword(mapping, banks_dir)
    case _:
        break

# After:
action_choices = ["Add keyword", "Remove keyword", "Back"]
action = select_option("Select action", action_choices, default="Back")

match action:
    case "Add keyword":
        add_keyword(mapping, banks_dir)
    case "Remove keyword":
        remove_keyword(mapping, banks_dir)
    case _:
        break
```

**Replace keyword removal selection** (lines 65-70):
```python
# Before:
choices = [str(i) for i in range(1, len(mapping.blacklist_keywords) + 1)]
choice = Prompt.ask(
    "\nSelect keyword number to remove (or press Enter to cancel)",
    choices=[*choices, ""],
    default="",
)

if not choice:
    console.print("[dim]Cancelled[/dim]")
    return

keyword = mapping.blacklist_keywords.pop(int(choice) - 1)

# After:
keyword_choices = [*mapping.blacklist_keywords, "(Cancel)"]
selected = select_option("Select keyword to remove", keyword_choices, default="(Cancel)")

if selected == "(Cancel)":
    console.print("[dim]Cancelled[/dim]")
    return

mapping.blacklist_keywords.remove(selected)
keyword = selected
```

#### 2. Update Blacklist Tests
**File**: `tests/unit/test_blacklist_cli.py`
**Changes**: Update mocks to use select_option instead of Prompt.ask

```python
# Update imports
from budget_tracker.cli.blacklist import (
    list_available_banks,
    display_blacklist,
    add_keyword,
    remove_keyword,
)

# Update test_remove_keyword
@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.select_option")
def test_remove_keyword(mock_select, mock_save, sample_mapping, tmp_path):
    """Test removing a keyword from the blacklist."""
    mock_select.return_value = "MobilePay"  # Select the keyword directly

    remove_keyword(sample_mapping, tmp_path)

    assert "MobilePay" not in sample_mapping.blacklist_keywords
    assert "Visa" in sample_mapping.blacklist_keywords
    mock_save.assert_called_once()


@patch("budget_tracker.cli.blacklist.select_option")
def test_remove_keyword_cancelled(mock_select, sample_mapping, tmp_path):
    """Test cancelling keyword removal."""
    mock_select.return_value = "(Cancel)"

    original_keywords = sample_mapping.blacklist_keywords.copy()
    remove_keyword(sample_mapping, tmp_path)

    assert sample_mapping.blacklist_keywords == original_keywords
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`
- [x] Tests pass: `pytest tests/unit/test_blacklist_cli.py -v`
- [x] All tests pass: `pytest tests/`

#### Manual Verification:
- [ ] `budget-tracker blacklist` shows arrow-key navigation
- [ ] Can navigate with Up/Down arrows and Enter
- [ ] Can type numbers to select directly (1, 2, 3)
- [ ] Can use j/k for vim-style navigation
- [ ] `BUDGET_TRACKER_NO_INTERACTIVE=1 budget-tracker blacklist` shows Rich fallback

**Note**: Pause for manual confirmation before marking complete.

---

## Phase 4: Fix Typo in Blacklist

### Overview
Fix the "Abailable" typo noticed in blacklist.py line 116.

### Changes Required:

**File**: `src/budget_tracker/cli/blacklist.py`
**Line 116**: Change `"Abailable banks"` to `"Available banks"`

Note: This line will be removed in Phase 3, so this fix is optional if Phase 3 is completed.

---

## Testing Strategy

### Unit Tests:
- `test_selection.py::TestIsInteractiveTerminal` - Terminal detection logic
- `test_selection.py::TestSelectOption` - Routing between questionary/Rich
- `test_selection.py::TestRichSelect` - Fallback behavior
- `test_blacklist_cli.py` - Updated tests for select_option usage

### Manual Testing:
1. Run `budget-tracker blacklist` in a normal terminal
2. Verify arrow keys move selection highlight up/down
3. Verify pressing Enter selects the highlighted option
4. Verify typing "1", "2", "3" selects options directly
5. Verify j/k keys work for navigation
6. Run with `BUDGET_TRACKER_NO_INTERACTIVE=1` and verify numbered menu appears
7. Run with `TERM=dumb` and verify fallback works

### Integration Testing:
- Existing CLI integration tests should still pass
- Blacklist functionality unchanged, just improved UX

## References
- questionary docs: https://questionary.readthedocs.io/
- prompt_toolkit dumb terminal issue: https://github.com/prompt-toolkit/python-prompt-toolkit/issues/1032
- Current blacklist implementation: `src/budget_tracker/cli/blacklist.py`
- Existing plan: `.claude/thoughts/shared/plans/2026-01-17-interactive-blacklist-cli.md`
