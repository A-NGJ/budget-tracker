# Interactive Blacklist CLI Implementation Plan

## Overview
Add an interactive CLI command `blacklist` that provides a menu-driven interface for managing `blacklist_keywords` in per-bank configurations.

## Current State Analysis
- `BankMapping` model has `blacklist_keywords: list[str]` field (`src/budget_tracker/models/bank_mapping.py:25`)
- Bank configs stored as YAML in `config/banks/*.yaml` with existing `blacklist_keywords: []`
- `load_mapping()` and `save_mapping()` exist in `src/budget_tracker/cli/mapping.py:199-218`
- CLI uses Typer with Rich for interactive prompts (Prompt.ask, Table, Console)

### Key Discoveries:
- Interactive patterns use `Prompt.ask()` with numbered choices (`confirmation.py:70-77`)
- Table display pattern exists in `transfer_confirmation.py:33-59`
- While loops used for repeated interactions (`mapping.py:46-67`)

## Desired End State
- User can run `budget-tracker blacklist` to enter interactive management mode
- Menu-driven flow: select bank → add/remove/list keywords → repeat or exit
- Changes saved immediately to bank YAML files

## What We're NOT Doing
- Global blacklist (config/blacklist.txt) - out of scope
- Flag-based CLI arguments (--add, --remove)
- Automatic blacklist application during processing (separate task)

## Implementation Approach
Create a new `blacklist.py` module with interactive functions, then wire up a simple command in `main.py`.

---

## Phase 1: Create Interactive Blacklist Module

### Overview
Create the interactive blacklist management functions in a new module.

### Changes Required:

#### 1. New Blacklist Management Module
**File**: `src/budget_tracker/cli/blacklist.py`
**Changes**: Create new file with interactive management functions

```python
"""Interactive blacklist management for bank configurations."""

from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from budget_tracker.cli.mapping import load_mapping, save_mapping
from budget_tracker.models.bank_mapping import BankMapping

console = Console()


def list_available_banks(banks_dir: Path) -> list[str]:
    """Get list of configured bank names."""
    if not banks_dir.exists():
        return []
    return sorted([f.stem for f in banks_dir.glob("*.yaml")])


def display_blacklist(mapping: BankMapping) -> None:
    """Display current blacklist keywords for a bank."""
    console.print(f"\n[bold]Blacklist for {mapping.bank_name}:[/bold]")

    if not mapping.blacklist_keywords:
        console.print("  [dim](empty)[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim")
    table.add_column("Keyword")

    for i, keyword in enumerate(mapping.blacklist_keywords, 1):
        table.add_row(str(i), keyword)

    console.print(table)


def add_keyword(mapping: BankMapping, banks_dir: Path) -> None:
    """Add a keyword to the blacklist."""
    keyword = Prompt.ask("\nEnter keyword to add")

    if not keyword.strip():
        console.print("[yellow]No keyword entered[/yellow]")
        return

    keyword = keyword.strip()

    if keyword in mapping.blacklist_keywords:
        console.print(f"[yellow]'{keyword}' is already in the blacklist[/yellow]")
        return

    mapping.blacklist_keywords.append(keyword)
    save_mapping(mapping, banks_dir)
    console.print(f"[green]✓[/green] Added '{keyword}' to {mapping.bank_name} blacklist")


def remove_keyword(mapping: BankMapping, banks_dir: Path) -> None:
    """Remove a keyword from the blacklist."""
    if not mapping.blacklist_keywords:
        console.print("[yellow]Blacklist is empty, nothing to remove[/yellow]")
        return

    display_blacklist(mapping)

    choices = [str(i) for i in range(1, len(mapping.blacklist_keywords) + 1)]
    choice = Prompt.ask(
        "\nSelect keyword number to remove (or press Enter to cancel)",
        choices=choices + [""],
        default="",
    )

    if not choice:
        console.print("[dim]Cancelled[/dim]")
        return

    keyword = mapping.blacklist_keywords.pop(int(choice) - 1)
    save_mapping(mapping, banks_dir)
    console.print(f"[green]✓[/green] Removed '{keyword}' from {mapping.bank_name} blacklist")


def manage_bank_blacklist(mapping: BankMapping, banks_dir: Path) -> None:
    """Interactive submenu for managing a single bank's blacklist."""
    while True:
        display_blacklist(mapping)

        console.print("\n[bold]Select action:[/bold]")
        console.print("  1. Add keyword")
        console.print("  2. Remove keyword")
        console.print("  3. Back")

        choice = Prompt.ask("", choices=["1", "2", "3"], default="3")

        match choice:
            case "1":
                add_keyword(mapping, banks_dir)
            case "2":
                remove_keyword(mapping, banks_dir)
            case _:
                break


def interactive_blacklist_management(banks_dir: Path) -> None:
    """Main entry point for interactive blacklist management."""
    console.print("\n[bold]Blacklist Management[/bold]")

    while True:
        banks = list_available_banks(banks_dir)

        if not banks:
            console.print("[yellow]No bank configurations found.[/yellow]")
            console.print("Run 'budget-tracker process' with a CSV file to create a bank mapping first.")
            return

        console.print("\n[bold]Available banks:[/bold]")
        for i, bank in enumerate(banks, 1):
            console.print(f"  {i}. {bank}")
        console.print(f"  {len(banks) + 1}. Exit")

        choices = [str(i) for i in range(1, len(banks) + 2)]
        choice = Prompt.ask("Select bank", choices=choices, default=str(len(banks) + 1))

        if int(choice) == len(banks) + 1:
            console.print("[dim]Exiting blacklist management[/dim]")
            break

        bank_name = banks[int(choice) - 1]
        mapping = load_mapping(bank_name, banks_dir)

        if not mapping:
            console.print(f"[red]Failed to load mapping for {bank_name}[/red]")
            continue

        manage_bank_blacklist(mapping, banks_dir)
```

#### 2. Unit Tests for Blacklist Module
**File**: `tests/unit/test_blacklist_cli.py`
**Changes**: Create new test file

```python
"""Tests for interactive blacklist management."""

import pytest
from unittest.mock import patch, MagicMock

from budget_tracker.cli.blacklist import (
    list_available_banks,
    display_blacklist,
    add_keyword,
    remove_keyword,
)
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


@pytest.fixture
def sample_mapping():
    """Create a sample bank mapping for testing."""
    return BankMapping(
        bank_name="test_bank",
        column_mapping=ColumnMapping(
            date_column="Date",
            amount_column="Amount",
            description_columns=["Description"],
        ),
        blacklist_keywords=["MobilePay", "Visa"],
    )


@pytest.fixture
def empty_mapping():
    """Create a bank mapping with empty blacklist."""
    return BankMapping(
        bank_name="empty_bank",
        column_mapping=ColumnMapping(
            date_column="Date",
            amount_column="Amount",
            description_columns=["Description"],
        ),
        blacklist_keywords=[],
    )


def test_list_available_banks(tmp_path):
    """Test listing available bank configurations."""
    # Create mock bank files
    (tmp_path / "danske_bank.yaml").touch()
    (tmp_path / "nordea.yaml").touch()

    banks = list_available_banks(tmp_path)

    assert banks == ["danske_bank", "nordea"]


def test_list_available_banks_empty_dir(tmp_path):
    """Test listing banks when directory is empty."""
    banks = list_available_banks(tmp_path)
    assert banks == []


def test_list_available_banks_nonexistent_dir(tmp_path):
    """Test listing banks when directory doesn't exist."""
    banks = list_available_banks(tmp_path / "nonexistent")
    assert banks == []


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_keyword(mock_prompt, mock_save, sample_mapping, tmp_path):
    """Test adding a keyword to the blacklist."""
    mock_prompt.return_value = "NewKeyword"

    add_keyword(sample_mapping, tmp_path)

    assert "NewKeyword" in sample_mapping.blacklist_keywords
    mock_save.assert_called_once_with(sample_mapping, tmp_path)


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_duplicate_keyword(mock_prompt, mock_save, sample_mapping, tmp_path):
    """Test adding a duplicate keyword shows warning."""
    mock_prompt.return_value = "MobilePay"  # Already exists

    add_keyword(sample_mapping, tmp_path)

    # Should not save since keyword already exists
    mock_save.assert_not_called()
    # Should still have only one instance
    assert sample_mapping.blacklist_keywords.count("MobilePay") == 1


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_empty_keyword(mock_prompt, mock_save, sample_mapping, tmp_path):
    """Test adding empty keyword is rejected."""
    mock_prompt.return_value = "   "

    add_keyword(sample_mapping, tmp_path)

    mock_save.assert_not_called()


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_remove_keyword(mock_prompt, mock_save, sample_mapping, tmp_path):
    """Test removing a keyword from the blacklist."""
    mock_prompt.return_value = "1"  # Remove first keyword (MobilePay)

    remove_keyword(sample_mapping, tmp_path)

    assert "MobilePay" not in sample_mapping.blacklist_keywords
    assert "Visa" in sample_mapping.blacklist_keywords
    mock_save.assert_called_once()


@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_remove_keyword_cancelled(mock_prompt, sample_mapping, tmp_path):
    """Test cancelling keyword removal."""
    mock_prompt.return_value = ""  # Press Enter to cancel

    original_keywords = sample_mapping.blacklist_keywords.copy()
    remove_keyword(sample_mapping, tmp_path)

    assert sample_mapping.blacklist_keywords == original_keywords


def test_remove_keyword_empty_blacklist(empty_mapping, tmp_path, capsys):
    """Test removing from empty blacklist shows message."""
    remove_keyword(empty_mapping, tmp_path)
    # Function should return early without prompting
```

### Success Criteria:

#### Automated Verification:
- [ ] Type checking: `ty check`
- [ ] Linting: `ruff check`
- [ ] Formatting: `ruff format --check`
- [ ] Tests pass: `pytest tests/unit/test_blacklist_cli.py`

#### Manual Verification:
- [ ] Functions can be imported without error

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Wire Up CLI Command

### Overview
Add the `blacklist` command to the main CLI that calls the interactive module.

### Changes Required:

#### 1. Add Blacklist Command to Main CLI
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Add import and new command

Add import at top:
```python
from budget_tracker.cli.blacklist import interactive_blacklist_management
```

Add command after `list_mappings` (around line 246):
```python
@app.command()
def blacklist(ctx: typer.Context) -> None:
    """Interactively manage blacklist keywords for bank configurations."""
    settings: Settings = ctx.obj["settings"]
    interactive_blacklist_management(settings.banks_dir)
```

#### 2. Update CLI Package Exports
**File**: `src/budget_tracker/cli/__init__.py`
**Changes**: Add blacklist module to exports (if needed)

### Success Criteria:

#### Automated Verification:
- [ ] Type checking: `ty check`
- [ ] Linting: `ruff check`
- [ ] Tests pass: `pytest tests/`

#### Manual Verification:
- [ ] `budget-tracker --help` shows `blacklist` command
- [ ] `budget-tracker blacklist` enters interactive mode
- [ ] Can select a bank and see its blacklist
- [ ] Can add a keyword and see it saved to YAML
- [ ] Can remove a keyword
- [ ] Can exit cleanly

**Note**: Pause for manual confirmation before marking complete.

---

## Testing Strategy

### Unit Tests:
- `test_list_available_banks` - verify bank discovery
- `test_add_keyword` - verify keyword addition and save
- `test_add_duplicate_keyword` - verify duplicate rejection
- `test_remove_keyword` - verify keyword removal and save
- `test_remove_keyword_cancelled` - verify cancel handling

### Manual Testing:
1. Run `budget-tracker blacklist`
2. Select a bank (e.g., `danske_bank`)
3. Add keyword "TestKeyword"
4. Verify `config/banks/danske_bank.yaml` contains `TestKeyword` in `blacklist_keywords`
5. Remove the keyword
6. Verify it's removed from YAML
7. Exit and re-enter to confirm persistence

## References
- Existing interactive patterns: `src/budget_tracker/cli/confirmation.py`, `mapping.py`
- BankMapping model: `src/budget_tracker/models/bank_mapping.py:15-31`
- Bank config example: `config/banks/danske_bank.yaml`
