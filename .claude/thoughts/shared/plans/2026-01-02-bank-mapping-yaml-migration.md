# Bank Mapping YAML Migration Implementation Plan

## Overview

Migrate bank mapping storage from a single `config/bank_mappings.json` file to per-bank YAML files in `config/banks/` directory. The CLI will use an explicit `--bank` flag instead of filename auto-matching.

## Current State Analysis

### Key Files
- `config/bank_mappings.json` - Single JSON file with all bank mappings
- `src/budget_tracker/cli/mapping.py:182-208` - `save_mapping()` and `load_mapping()` functions
- `src/budget_tracker/config/settings.py:19` - `mappings_file` path definition
- `src/budget_tracker/cli/main.py:86` - Mapping loading in `process` command
- `src/budget_tracker/cli/main.py:159-173` - `list-mappings` command

### Current Behavior
- All mappings stored in one JSON file keyed by `bank_name`
- `load_mapping()` uses fuzzy substring matching: `name.lower() in bank_name.lower()`
- `save_mapping()` merges new mapping into existing JSON
- CLI auto-matches mapping by CSV filename

## Desired End State

```
config/
├── banks/
│   ├── danske_bank.yaml
│   ├── nordea.yaml
│   └── revolut.yaml
└── categories.yaml
```

### New CLI Behavior
```bash
# Explicit bank specification
budget-tracker process statement.csv --bank danske_bank

# List available banks
budget-tracker list-mappings
# Output: danske_bank, nordea, revolut

# Interactive mapping creates new YAML file
budget-tracker process new_bank_statement.csv --bank new_bank
# Creates: config/banks/new_bank.yaml
```

### YAML File Format
```yaml
# config/banks/danske_bank.yaml
bank_name: danske_bank

column_mapping:
  date_column: Dato
  amount_column: Beløb
  description_columns:
    - Kategori
    - Underkategori
    - Tekst
  currency_column: null

date_format: "%d.%m.%Y"
decimal_separator: ","
default_currency: DKK

blacklist_keywords:
  - MobilePay
```

## What We're NOT Doing

- No TOML support (YAML only)
- No backwards compatibility period (clean cutover)
- No changes to `BankMapping` Pydantic model
- No changes to `CSVParser` or how mappings are consumed

## Implementation Approach

1. Update settings to use directory path instead of file path
2. Create new YAML-based load/save functions
3. Add `--bank` flag to `process` command
4. Update `list-mappings` to scan directory
5. Migrate existing JSON data to YAML files
6. Update tests

---

## Phase 1: Settings and YAML Infrastructure

### Overview
Update settings to use a directory path and create YAML-based loading/saving functions.

### Changes Required:

#### 1. Update Settings
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Replace `mappings_file: Path` with `banks_dir: Path`

```python
# Line 19: Change from
mappings_file: Path = Path.cwd() / "config" / "bank_mappings.json"

# To
banks_dir: Path = Path.cwd() / "config" / "banks"
```

#### 2. Update ensure_directories
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Add `banks_dir` to directory creation

```python
# Lines 33-35: Update to include banks_dir
def ensure_directories(self) -> None:
    """Ensure required directories exist."""
    self.config_dir.mkdir(parents=True, exist_ok=True)
    self.data_dir.mkdir(parents=True, exist_ok=True)
    self.output_dir.mkdir(parents=True, exist_ok=True)
    self.banks_dir.mkdir(parents=True, exist_ok=True)
```

#### 3. Create YAML load function
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Replace `load_mapping()` with YAML-based version

```python
def load_mapping(bank_name: str, banks_dir: Path) -> BankMapping | None:
    """Load bank mapping from YAML file.

    Args:
        bank_name: Exact bank name (matches filename without .yaml)
        banks_dir: Directory containing bank YAML files

    Returns:
        BankMapping if found, None otherwise
    """
    mapping_file = banks_dir / f"{bank_name}.yaml"

    if not mapping_file.exists():
        return None

    with mapping_file.open() as f:
        data = yaml.safe_load(f)

    return BankMapping(**data)
```

#### 4. Create YAML save function
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Replace `save_mapping()` with YAML-based version

```python
def save_mapping(mapping: BankMapping, banks_dir: Path) -> None:
    """Save bank mapping to YAML file.

    Args:
        mapping: BankMapping to save
        banks_dir: Directory to save YAML file in
    """
    banks_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = banks_dir / f"{mapping.bank_name}.yaml"

    with mapping_file.open("w") as f:
        yaml.safe_dump(mapping.model_dump(), f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]✓[/green] Mapping saved to {mapping_file}")
```

#### 5. Add yaml import
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add yaml import at top of file

```python
import yaml
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] Linting passes: `ruff check`
- [x] Format check passes: `ruff format --check`

#### Manual Verification:
- [x] Unit test for new `load_mapping()` function works
- [x] Unit test for new `save_mapping()` function works

**Note**: Pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: CLI Updates

### Overview
Add `--bank` flag to `process` command and update `list-mappings` to scan directory.

### Changes Required:

#### 1. Add --bank flag to process command
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Add required `--bank` parameter and update mapping loading

```python
# Update process command signature (around line 48)
@app.command()
def process(
    ctx: typer.Context,
    files: Annotated[list[Path], typer.Argument(help="CSV files to process")],
    bank: Annotated[str, typer.Option("--bank", "-b", help="Bank name for mapping lookup")] = "",
) -> None:
    """Process bank statement CSV files and categorize transactions."""
```

#### 2. Update mapping loading logic
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Use explicit bank name instead of file.stem

```python
# Around lines 82-98: Update the mapping loading section
for file in files:
    console.print(f"\n[cyan]Processing:[/cyan] {file.name}")

    # Require bank name for mapping lookup
    if not bank:
        console.print("[red]Error:[/red] --bank flag is required")
        console.print("Usage: budget-tracker process file.csv --bank <bank_name>")
        console.print("Run 'budget-tracker list-mappings' to see available banks")
        raise typer.Exit(1)

    # Try to load saved mapping
    mapping = load_mapping(bank, settings.banks_dir)

    if not mapping:
        # Interactive column mapping
        _, columns = parser.parse_file(file)
        console.print(f"Detected {len(columns)} columns: {', '.join(columns)}")
        console.print(f"[yellow]No mapping found for '{bank}'. Creating new mapping...[/yellow]")

        mapping = interactive_column_mapping(file, columns, bank_name=bank)
        if not mapping:
            console.print("[red]Mapping cancelled[/red]")
            raise typer.Exit(1)

        save_mapping(mapping, settings.banks_dir)
    else:
        console.print(f"[green]✓[/green] Using saved mapping for {mapping.bank_name}")
```

#### 3. Update interactive_column_mapping to accept bank_name
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add `bank_name` parameter to function signature

```python
# Around line 13: Update function signature
def interactive_column_mapping(
    file_path: Path,
    columns: list[str],
    bank_name: str | None = None,
) -> BankMapping | None:
```

```python
# Around line 152: Use provided bank_name or prompt for it
if bank_name:
    final_bank_name = bank_name
else:
    final_bank_name = Prompt.ask("Enter bank name for this mapping", default=file_path.stem)
```

#### 4. Update list-mappings command
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Scan directory for YAML files instead of parsing JSON

```python
@app.command()
def list_mappings(ctx: typer.Context) -> None:
    """List all saved bank mappings"""
    settings: Settings = ctx.obj["settings"]

    if not settings.banks_dir.exists():
        console.print("No saved mappings found.")
        return

    yaml_files = list(settings.banks_dir.glob("*.yaml"))

    if not yaml_files:
        console.print("No saved mappings found.")
        return

    console.print("\n[bold]Saved Bank Mappings:[/bold]")
    for yaml_file in sorted(yaml_files):
        bank_name = yaml_file.stem
        console.print(f"  • {bank_name}")
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] Linting passes: `ruff check`
- [x] Format check passes: `ruff format --check`

#### Manual Verification:
- [x] `budget-tracker process file.csv --bank test` works
- [x] `budget-tracker list-mappings` shows YAML files from directory
- [x] Error shown when `--bank` flag missing

**Note**: Pause for manual confirmation before proceeding to Phase 3.

---

## Phase 3: Migration and Cleanup

### Overview
Migrate existing JSON data to YAML files and remove JSON support.

### Changes Required:

#### 1. Create migration script
**File**: `scripts/migrate_bank_mappings.py` (new file)
**Purpose**: One-time migration of existing JSON to YAML

```python
#!/usr/bin/env python3
"""Migrate bank_mappings.json to individual YAML files."""

import json
from pathlib import Path

import yaml


def migrate() -> None:
    """Migrate bank_mappings.json to config/banks/*.yaml"""
    json_file = Path("config/bank_mappings.json")
    banks_dir = Path("config/banks")

    if not json_file.exists():
        print("No bank_mappings.json found, nothing to migrate")
        return

    banks_dir.mkdir(parents=True, exist_ok=True)

    with json_file.open() as f:
        mappings = json.load(f)

    for bank_name, mapping_data in mappings.items():
        yaml_file = banks_dir / f"{bank_name}.yaml"

        with yaml_file.open("w") as f:
            yaml.safe_dump(mapping_data, f, default_flow_style=False, sort_keys=False)

        print(f"Created {yaml_file}")

    print(f"\nMigration complete. You can now delete {json_file}")


if __name__ == "__main__":
    migrate()
```

#### 2. Run migration
```bash
python scripts/migrate_bank_mappings.py
```

#### 3. Delete old JSON file
```bash
rm config/bank_mappings.json
```

#### 4. Update .gitignore if needed
Remove any JSON-specific ignores for bank mappings if present.

### Success Criteria:

#### Automated Verification:
- [x] `config/banks/danske_bank.yaml` exists with correct content
- [x] `config/bank_mappings.json` deleted

#### Manual Verification:
- [x] `budget-tracker list-mappings` shows migrated banks
- [x] Processing with migrated mapping works

**Note**: Pause for manual confirmation before proceeding to Phase 4.

---

## Phase 4: Update Tests

### Overview
Update integration tests to use new YAML-based configuration.

### Changes Required:

#### 1. Update sample_mapping fixture
**File**: `tests/integration/test_end_to_end.py`
**Changes**: Create YAML file instead of JSON

```python
@pytest.fixture
def sample_mapping(self, tmp_path: Path) -> Path:
    """Create a sample bank mapping directory with YAML file"""
    banks_dir = tmp_path / "banks"
    banks_dir.mkdir()

    mapping_data = {
        "bank_name": "test_bank",
        "column_mapping": {
            "date_column": "Date",
            "amount_column": "Amount",
            "description_columns": ["Description"],
            "currency_column": None,
        },
        "date_format": "%Y-%m-%d",
        "decimal_separator": ".",
        "default_currency": "DKK",
    }

    yaml_file = banks_dir / "test_bank.yaml"
    yaml_file.write_text(yaml.safe_dump(mapping_data))

    return banks_dir
```

#### 2. Update test_list_mappings_empty
**File**: `tests/integration/test_end_to_end.py`
**Changes**: Use banks_dir instead of mappings_file

```python
def test_list_mappings_empty(self, tmp_path: Path) -> None:
    """Test listing mappings when none exist"""
    banks_dir = tmp_path / "banks"
    # Don't create directory - should handle non-existent directory

    test_settings = Settings()
    test_settings.banks_dir = banks_dir

    test_app = create_app(settings=test_settings)

    result = runner.invoke(test_app, ["list-mappings"])
    assert result.exit_code == 0
    assert "No saved mappings found" in result.output
```

#### 3. Update test_list_mappings_with_data
**File**: `tests/integration/test_end_to_end.py`
**Changes**: Use banks_dir fixture

```python
def test_list_mappings_with_data(self, sample_mapping: Path) -> None:
    """Test listing mappings when they exist"""
    test_settings = Settings()
    test_settings.banks_dir = sample_mapping

    test_app = create_app(settings=test_settings)

    result = runner.invoke(test_app, ["list-mappings"])
    assert result.exit_code == 0
    assert "test_bank" in result.output
```

#### 4. Add yaml import to test file
**File**: `tests/integration/test_end_to_end.py`

```python
import yaml
```

### Success Criteria:

#### Automated Verification:
- [x] All tests pass: `pytest`
- [x] Type checking passes: `ty check`
- [x] Linting passes: `ruff check`

#### Manual Verification:
- [x] Integration tests cover new YAML behavior
- [x] Edge cases (missing directory, empty directory) handled

---

## Testing Strategy

### Unit Tests

**New tests to add in `tests/unit/test_mapping.py`:**

```python
class TestBankMappingYAML:
    def test_save_mapping_creates_yaml_file(self, tmp_path: Path) -> None:
        """Test that save_mapping creates YAML file."""
        banks_dir = tmp_path / "banks"
        mapping = BankMapping(
            bank_name="test_bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_columns=["Desc"],
            ),
        )

        save_mapping(mapping, banks_dir)

        yaml_file = banks_dir / "test_bank.yaml"
        assert yaml_file.exists()

        with yaml_file.open() as f:
            data = yaml.safe_load(f)
        assert data["bank_name"] == "test_bank"

    def test_load_mapping_reads_yaml_file(self, tmp_path: Path) -> None:
        """Test that load_mapping reads YAML file."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        yaml_file = banks_dir / "test_bank.yaml"
        yaml_file.write_text(yaml.safe_dump({
            "bank_name": "test_bank",
            "column_mapping": {
                "date_column": "Date",
                "amount_column": "Amount",
                "description_columns": ["Desc"],
            },
        }))

        mapping = load_mapping("test_bank", banks_dir)

        assert mapping is not None
        assert mapping.bank_name == "test_bank"

    def test_load_mapping_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Test that load_mapping returns None for missing bank."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        mapping = load_mapping("nonexistent", banks_dir)

        assert mapping is None
```

### Manual Testing

1. Run migration script on current JSON
2. Verify `list-mappings` shows migrated banks
3. Process a CSV with `--bank danske_bank`
4. Create new mapping with `--bank new_bank`
5. Verify new YAML file created correctly

## References

- Research document: `.claude/thoughts/shared/research/2026-01-02-bank-mapping-config-format-extension.md`
- Current JSON structure: `config/bank_mappings.json`
- YAML pattern example: `src/budget_tracker/config/settings.py:28-31`
