---
date: 2026-01-02T12:00:00+0000
researcher: Claude Code
git_commit: 7b9faecfba9b5daa8719b0bb3010ec289ded9d15
branch: main
repository: budget-tracker
topic: "Bank Mapping Configuration Format Extension Analysis"
tags: [research, codebase, configuration, bank-mappings, yaml, toml, json]
status: complete
last_updated: 2026-01-02
last_updated_by: Claude Code
---

# Research: Bank Mapping Configuration Format Extension Analysis

**Date**: 2026-01-02T12:00:00+0000
**Researcher**: Claude Code
**Git Commit**: 7b9faecfba9b5daa8719b0bb3010ec289ded9d15
**Branch**: main
**Repository**: budget-tracker

## Research Question

Analysis of the current bank statement configuration system for the possibility of extending the project to accept any bank statement defined in its own YAML or TOML setting file, replacing the current JSON-based configuration.

## Summary

The budget-tracker project currently uses JSON for bank mappings (`config/bank_mappings.json`) and YAML for categories (`config/categories.yaml`). The configuration system is modular with clear separation between Pydantic models, loading/saving functions, and settings management. The project already has PyYAML as a dependency and uses it for categories. Extension to per-bank YAML or TOML files is architecturally straightforward as the loading/saving logic is isolated in `src/budget_tracker/cli/mapping.py`.

## Detailed Findings

### Current Configuration Architecture

#### Configuration Files

| File | Format | Purpose | Location |
|------|--------|---------|----------|
| `bank_mappings.json` | JSON | All bank CSV column mappings | `config/bank_mappings.json` |
| `categories.yaml` | YAML | Transaction categories/subcategories | `config/categories.yaml` |
| `pyproject.toml` | TOML | Project metadata and tool config | `pyproject.toml` |

#### Bank Mapping Data Model

The `BankMapping` Pydantic model (`src/budget_tracker/models/bank_mapping.py:15-31`) defines the structure:

```python
class ColumnMapping(BaseModel):
    date_column: str
    amount_column: str
    description_columns: list[str]
    currency_column: str | None = None

class BankMapping(BaseModel):
    bank_name: str
    column_mapping: ColumnMapping
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    default_currency: str = "DKK"
    blacklist_keywords: list[str] = Field(default_factory=list)
```

#### Current JSON Structure

The current `bank_mappings.json` (`config/bank_mappings.json:1-15`) stores all banks in a single file:

```json
{
  "danske_bank": {
    "bank_name": "danske_bank",
    "column_mapping": {
      "date_column": "Dato",
      "amount_column": "Beløb",
      "description_columns": ["Kategori", "Underkategori", "Tekst"],
      "currency_column": null
    },
    "date_format": "%d.%m.%Y",
    "decimal_separator": ",",
    "default_currency": "DKK",
    "blacklist_keywords": ["MobilePay"]
  }
}
```

### Configuration Loading/Saving Code

#### Loading Function (`src/budget_tracker/cli/mapping.py:197-208`)

```python
def load_mapping(bank_name: str, mappings_file: Path) -> BankMapping | None:
    """Load saved bank mapping by name"""
    if not mappings_file.exists():
        return None

    with mappings_file.open() as f:
        mappings = json.load(f)

    for name in mappings:
        if name.lower() in bank_name.lower():
            return BankMapping(**mappings[name])
    return None
```

Key aspects:
- Uses `json.load()` for file parsing
- Case-insensitive substring matching for bank name lookup
- Constructs Pydantic model via `BankMapping(**dict)`

#### Saving Function (`src/budget_tracker/cli/mapping.py:182-194`)

```python
def save_mapping(mapping: BankMapping, mappings_file: Path) -> None:
    """Save bank mapping to JSON file"""
    mappings: dict[str, dict[str, object]] = {}
    if mappings_file.exists():
        with mappings_file.open() as f:
            mappings = json.load(f)

    mappings[mapping.bank_name] = mapping.model_dump()

    with mappings_file.open("w") as f:
        json.dump(mappings, f, indent=2)
```

Key aspects:
- Uses Pydantic's `model_dump()` for serialization
- Merges new mapping into existing file
- Uses `json.dump()` with `indent=2` for formatting

#### Settings Path Definition (`src/budget_tracker/config/settings.py:19`)

```python
mappings_file: Path = Path.cwd() / "config" / "bank_mappings.json"
```

### Existing YAML Usage

The project already uses YAML for categories (`src/budget_tracker/config/settings.py:28-31`):

```python
def load_categories(self) -> dict[str, Any]:
    """Load categories from YAML file."""
    with self.categories_file.open() as f:
        return yaml.safe_load(f)
```

The categories YAML structure (`config/categories.yaml:1-89`):

```yaml
categories:
  - name: "Food & Drinks"
    subcategories:
      - "Groceries"
      - "Restaurants"
      - "Coffee & Cafes"
      - "Other"
  # ... more categories
```

### Current Dependencies

From `pyproject.toml:11-20`:

```toml
dependencies = [
    "typer[all]>=0.12.0",
    "pandas>=2.2.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.3.0",
    "ollama>=0.3.0",
    "pyyaml>=6.0.1",      # Already included
    "rich>=13.7.0",
    "httpx>=0.27.0",
]
```

**PyYAML is already a dependency** - no new dependencies needed for YAML support.

### How Bank Mappings Are Consumed

The `CSVParser.load_with_mapping()` method (`src/budget_tracker/parsers/csv_parser.py:70-130`) uses `BankMapping` fields:

- `mapping.column_mapping.date_column` - line 82
- `mapping.column_mapping.amount_column` - line 83
- `mapping.date_format` - line 90
- `mapping.decimal_separator` - line 93
- `mapping.column_mapping.currency_column` - line 96
- `mapping.default_currency` - line 101
- `mapping.column_mapping.description_columns` - line 105
- `mapping.remove_blacklist_keywords()` - line 109
- `mapping.bank_name` - line 120

The main CLI invokes mapping loading at `src/budget_tracker/cli/main.py:86`:

```python
mapping = load_mapping(file.stem, settings.mappings_file)
```

### Format Comparison

#### YAML Format Example

Equivalent bank mapping in YAML would be more readable:

```yaml
# danske_bank.yaml
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

#### TOML Format Example

Equivalent in TOML:

```toml
# danske_bank.toml
bank_name = "danske_bank"
date_format = "%d.%m.%Y"
decimal_separator = ","
default_currency = "DKK"
blacklist_keywords = ["MobilePay"]

[column_mapping]
date_column = "Dato"
amount_column = "Beløb"
description_columns = ["Kategori", "Underkategori", "Tekst"]
```

### Format Analysis

#### YAML

**Characteristics:**
- Indentation-based structure
- Supports comments with `#`
- Multi-line strings without escaping
- Null values with `null` or `~`
- Already used in this project for categories
- Already has dependency (pyyaml>=6.0.1)

**For this use case:**
- Consistent with existing `categories.yaml`
- Better for nested structures like `column_mapping`
- More readable for lists (description_columns)
- Single library for all config files

#### TOML

**Characteristics:**
- INI-like section headers `[section]`
- Reading: Built-in Python 3.11+ (`tomllib`)
- Writing: Requires additional library (`tomli-w` or `tomlkit`)
- Explicit quoting required for strings
- Clear section boundaries

**For this use case:**
- Project requires Python 3.12+ (pyproject.toml line 10)
- Reading available without new dependencies
- Writing would need new dependency
- Inline tables less readable for nested structures

### Extension Points for Multi-File Configuration

#### Current Single-File Architecture

```
config/
├── bank_mappings.json    # All banks in one file
└── categories.yaml
```

#### Potential Per-Bank File Architecture

```
config/
├── bank_mappings/
│   ├── danske_bank.yaml
│   ├── nordea.yaml
│   └── revolut.yaml
└── categories.yaml
```

#### Code Locations Requiring Changes

1. **Settings path definition** (`src/budget_tracker/config/settings.py:19`)
   - Change from single file path to directory path

2. **Load function** (`src/budget_tracker/cli/mapping.py:197-208`)
   - Scan directory for matching bank file
   - Parse YAML/TOML instead of JSON

3. **Save function** (`src/budget_tracker/cli/mapping.py:182-194`)
   - Write individual file per bank
   - Use YAML/TOML serialization

4. **List mappings command** (`src/budget_tracker/cli/main.py:159-173`)
   - List files in directory instead of parsing single JSON

### Pydantic Serialization Compatibility

Pydantic models support multiple serialization formats through `model_dump()`:

```python
# Current JSON serialization
mapping.model_dump()  # Returns dict

# For YAML: dump dict to yaml
yaml.safe_dump(mapping.model_dump())

# For loading from YAML/TOML
BankMapping(**yaml.safe_load(file))  # Works with any dict source
BankMapping.model_validate(data)     # Alternative with validation
```

## Code References

### Configuration Files
- `config/bank_mappings.json` - Current bank mapping storage
- `config/categories.yaml` - Existing YAML config example
- `pyproject.toml:17` - PyYAML dependency declaration

### Models
- `src/budget_tracker/models/bank_mapping.py:6-12` - ColumnMapping model
- `src/budget_tracker/models/bank_mapping.py:15-31` - BankMapping model

### Loading/Saving
- `src/budget_tracker/cli/mapping.py:182-194` - save_mapping() function
- `src/budget_tracker/cli/mapping.py:197-208` - load_mapping() function

### Settings
- `src/budget_tracker/config/settings.py:19` - mappings_file path definition
- `src/budget_tracker/config/settings.py:28-31` - YAML loading method

### Usage Sites
- `src/budget_tracker/cli/main.py:86` - Mapping loading in CLI
- `src/budget_tracker/cli/main.py:159-173` - List mappings command
- `src/budget_tracker/parsers/csv_parser.py:70-130` - BankMapping consumption

## Architecture Documentation

### Current Flow

```
User runs CLI
    ↓
main.py:86 calls load_mapping(file.stem, settings.mappings_file)
    ↓
mapping.py:197 reads JSON file
    ↓
mapping.py:207 creates BankMapping(**dict)
    ↓
csv_parser.py:70 uses BankMapping to parse CSV
```

### Interactive Creation Flow

```
User processes new bank CSV
    ↓
main.py:88 calls interactive_column_mapping()
    ↓
mapping.py:13 prompts user for column selections
    ↓
mapping.py:152 creates BankMapping object
    ↓
mapping.py:182 save_mapping() writes to JSON
```

### Serialization Pattern

The project uses a consistent pattern:
- **Pydantic models** define structure and validation
- **model_dump()** converts to dict for serialization
- **Model(**dict)** or **model_validate()** for deserialization
- **Format-specific libraries** handle file I/O (json, yaml)

This pattern works identically for JSON, YAML, or TOML since all serialize to/from Python dicts.

## Historical Context (from thoughts/)

### Related Research
- `.claude/thoughts/research/2025-10-14-general-codebase-functions.md` - Documents overall codebase architecture including configuration management

### Implementation Context
- The TDD implementation plan (`.claude/thoughts/plans/2025-10-10-bank-statement-normalizer-cli.md`) established the current JSON-based mapping storage in Phase 2

## Open Questions

1. **Single file vs directory?** - Should all banks remain in one file (simpler) or each bank get its own file (better for many banks, version control)?

Each bank gets its own file.

2. **YAML vs TOML?** - YAML is already used and more readable for nested data; TOML would need write dependency but is simpler for flat configs

YAML

3. **Migration strategy?** - How to handle existing `bank_mappings.json` during transition?

Migrate existing JSON to individual YAML files.

4. **Bank name matching?** - Current fuzzy matching (`name.lower() in bank_name.lower()`) needs consideration for file-based lookup

A user needs to specify bank name along with the file name when running the script.
