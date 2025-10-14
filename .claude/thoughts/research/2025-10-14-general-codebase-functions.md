---
date: 2025-10-14T09:05:02+0000
researcher: Claude Code
git_commit: fb8add8eb936f20554d0c93b63bead73aee30c19
branch: main
repository: budget-tracker
topic: "General codebase functions"
tags: [research, codebase, budget-tracker, cli, transaction-processing, llm-categorization, currency-conversion]
status: complete
last_updated: 2025-10-14
last_updated_by: Claude Code
---

# Research: General Codebase Functions

**Date**: 2025-10-14T09:05:02+0000
**Researcher**: Claude Code
**Git Commit**: fb8add8eb936f20554d0c93b63bead73aee30c19
**Branch**: main
**Repository**: budget-tracker

## Research Question

What are the general functions and capabilities of the budget-tracker codebase?

## Summary

The budget-tracker is a CLI application that standardizes bank statement transactions from various CSV formats into a unified format with automated LLM-based categorization. The application processes CSV files through a multi-stage pipeline: parsing with bank-specific column mappings, LLM categorization using local Ollama models, data normalization with currency conversion to DKK, user confirmation for uncertain categorizations, and export to standardized CSV format.

The codebase is built using Python with a test-driven development (TDD) approach, featuring six main functional areas: CLI interface (Typer + Rich), CSV parsing with auto-detection, transaction data models (Pydantic), LLM categorization (Ollama), currency conversion (Frankfurter API), and CSV export with summaries.

## Detailed Findings

### 1. Project Structure and Entry Points

**Main Entry Point**: `src/budget_tracker/cli/main.py:23`
- Command-line interface registered as `budget-tracker` console script in `pyproject.toml:34`
- Typer-based CLI with Rich for formatted output
- Entry point function: `budget_tracker.cli.main:app`

**Project Organization**:
```
src/budget_tracker/
├── cli/                    # Command-line interface (4 files)
├── models/                 # Data models (3 files)
├── parsers/                # CSV parsing (2 files)
├── normalizer/             # Data transformation (3 files)
├── categorizer/            # LLM categorization (2 files)
├── currency/               # Currency conversion (3 files)
├── exporters/              # CSV export (3 files)
├── config/                 # Settings management (2 files)
└── utils/                  # Utilities (1 file)
```

**Configuration Files**:
- `pyproject.toml` - Project metadata, dependencies, tool configurations (ruff, mypy, pytest)
- `config/bank_mappings.json` - Saved bank-specific column mappings
- `config/categories.yaml` - Category and subcategory definitions for LLM

**Key Dependencies**: Pydantic, Typer, Rich, pandas, httpx, ollama-python

### 2. CLI Commands and User Interface

**Available Commands**:

#### `process` Command (`src/budget_tracker/cli/main.py:23-136`)
Processes bank statement CSV files through the complete pipeline.

**Signature**: `process files... [--output PATH]`

**Pipeline Stages**:
1. **Validation** (lines 39-50): Checks Ollama server, ensures directories exist, validates input files
2. **Parsing & Mapping** (lines 54-81): Parses CSV with bank-specific column mappings, creates interactive mapping if needed
3. **LLM Categorization** (lines 83-97): Categorizes transactions using local Ollama LLM
4. **Normalization** (lines 99-118): Transforms to standard format with currency conversion to DKK
5. **Confirmation** (lines 120-124): Prompts user to review uncertain categorizations (confidence < 0.6)
6. **Export** (lines 126-135): Outputs standardized CSV and prints summary

#### `list-mappings` Command (`src/budget_tracker/cli/main.py:138-151`)
Displays all saved bank column mappings.

**Interactive Components**:

**Column Mapping** (`src/budget_tracker/cli/mapping.py:13-106`):
- Prompts user to map CSV columns to standard fields (date, amount, description, currency)
- Offers 6 predefined currencies (DKK, EUR, USD, GBP, SEK, NOK) plus custom option
- Saves mappings to JSON for reuse
- Case-insensitive bank name matching for loading saved mappings

**Category Confirmation** (`src/budget_tracker/cli/confirmation.py:11-62`):
- Reviews transactions with confidence < 0.6 threshold
- Offers three choices per transaction:
  - Accept: Keep LLM suggestion
  - Reject: Select from numbered category list
  - Skip: Mark as "Other/Uncategorized"
- Updates confidence to 1.0 for user-confirmed categories

### 3. Data Models and Transaction Handling

**Transaction Models** (`src/budget_tracker/models/transaction.py`):

#### `RawTransaction` (lines 37-44)
Represents unparsed CSV data before normalization.

**Fields**:
- `data: dict[str, Any]` - Raw CSV row as dictionary
- `source_file: str` - Source CSV file path
- `mapping: BankMapping` - Bank-specific column mapping
- `row_number: int | None` - Row number for error reporting

#### `StandardTransaction` (lines 12-35)
Represents normalized transaction in standard format.

**Fields**:
- `date: date` - Transaction date (parsed)
- `category: str` - Main category (validated non-empty)
- `subcategory: str | None` - Optional subcategory
- `amount: Decimal` - Amount in DKK (converted)
- `source: str` - Bank name
- `description: str | None` - Original description
- `confidence: float` - Categorization confidence (0.0-1.0)

**Configuration**: `ConfigDict(frozen=False)` allows post-creation modifications for LLM categorization updates.

**Bank Configuration Models** (`src/budget_tracker/models/bank_mapping.py`):

#### `ColumnMapping` (lines 6-13)
Maps CSV column names to standard fields.

**Fields**:
- `date_column: str`
- `amount_column: str`
- `description_column: str`
- `currency_column: str | None`

#### `BankMapping` (lines 15-25)
Complete bank configuration including column mappings and format settings.

**Fields**:
- `bank_name: str`
- `column_mapping: ColumnMapping`
- `date_format: str` (default: "%Y-%m-%d")
- `decimal_separator: str` (default: ".")
- `default_currency: str` (default: "DKK")

### 4. CSV Parsing and Data Processing

**CSV Parser** (`src/budget_tracker/parsers/csv_parser.py`):

**Auto-Detection Features**:
- **Encoding Detection** (lines 10-19): Tries UTF-8, falls back to ISO-8859-1
- **Delimiter Detection** (lines 22-31): Uses Python's `csv.Sniffer()` to detect comma vs semicolon

**Parser Methods**:

#### `parse_file()` (lines 37-54)
- Detects encoding and delimiter
- Reads CSV into pandas DataFrame (all columns as strings)
- Returns `tuple[pd.DataFrame, list[str]]` (data + column names)

#### `load_with_mapping()` (lines 56-83)
- Parses CSV and applies bank mapping
- Skips rows with missing date or amount
- Creates `RawTransaction` objects with row metadata
- Returns `list[RawTransaction]`

**Mapping Persistence**:
- **`save_mapping()`** (`src/budget_tracker/cli/mapping.py:109-121`): Saves to `config/bank_mappings.json`
- **`load_mapping()`** (`src/budget_tracker/cli/mapping.py:124-135`): Loads from JSON with case-insensitive bank name search

### 5. LLM Categorization System

**LLM Categorizer** (`src/budget_tracker/categorizer/llm_categorizer.py`):

**Configuration**:
- Uses local Ollama server at `http://localhost:11434` (configurable)
- Default model: `llama3.2:3b`
- Temperature: 0.1 (for consistent results)

**CategoryResult Model** (lines 9-32):
- Fields: `category`, `subcategory`, `confidence`, `needs_confirmation`
- Automatically sets `needs_confirmation = True` when `confidence < 0.6`

**Categorize Method** (lines 43-73):
- Builds prompt with available categories from `categories.yaml`
- Calls `ollama.generate()` with low temperature
- Parses JSON response: `{"category": "...", "subcategory": "...", "confidence": 0.0-1.0}`
- Falls back to "Other/Uncategorized" with 0.0 confidence on error

**Prompt Construction** (lines 79-103):
- Formats all categories and subcategories from YAML
- Provides confidence scoring guidelines:
  - 0.9-1.0: Very certain (e.g., "SPOTIFY.COM")
  - 0.7-0.9: Confident (e.g., "Cafe Central")
  - 0.4-0.7: Uncertain (needs confirmation)
  - 0.0-0.4: Very uncertain (use "Other/Uncategorized")
- Instructs to choose most specific subcategory

**Error Handling**:
- Catches all exceptions from Ollama API
- Handles markdown code blocks in responses
- Returns safe fallback on JSON parsing errors

### 6. Data Normalization and Currency Conversion

**Transaction Normalizer** (`src/budget_tracker/normalizer/transformer.py:9-91`):

**Normalization Process** (`normalize()` method, lines 15-73):

1. **Date Parsing** (lines 29-33):
   - Extracts date string from raw data
   - Uses `_parse_date()` with bank's date format
   - Returns `None` if invalid

2. **Amount Parsing** (lines 36-39):
   - Extracts amount string from raw data
   - Uses `_parse_amount()` with bank's decimal separator
   - Handles multiple thousand separator formats

3. **Currency Determination** (lines 42-47):
   - Reads from currency column if specified
   - Falls back to bank's default currency
   - Uppercases currency code

4. **Currency Conversion** (lines 50-55):
   - Converts all amounts to DKK
   - Uses historical exchange rates for transaction date
   - Returns `Decimal` rounded to 2 decimal places

5. **StandardTransaction Creation** (lines 60-68):
   - Combines parsed data with LLM categorization
   - Includes confidence score from LLM

**Helper Methods**:
- `_parse_date()` (lines 75-78): `datetime.strptime()` with format string
- `_parse_amount()` (lines 80-91): Handles comma/dot decimal separators, removes thousand separators

**Currency Converter** (`src/budget_tracker/currency/converter.py:7-41`):

**Convert Method** (lines 13-41):
- Optimizes same-currency transactions (returns unchanged)
- Gets historical exchange rate from provider
- Multiplies amount by rate
- Rounds to 2 decimal places using `ROUND_HALF_UP`

**Exchange Rate Provider** (`src/budget_tracker/currency/exchange_rate_provider.py:7-77`):

**API Integration**:
- Uses Frankfurter API: `https://api.frankfurter.app`
- Free, open-source API for European Central Bank rates
- Retrieves historical rates by date

**Caching**:
- In-memory cache: `dict[(from_currency, to_currency, date), Decimal]`
- Checked before API calls
- Reduces duplicate API requests

**Get Rate Method** (lines 21-72):
- Constructs URL: `{BASE_URL}/{date}?from={currency}&to={currency}`
- 10-second timeout
- Parses JSON response: `data["rates"][to_currency]`
- Raises `ValueError` on HTTP errors or invalid responses

### 7. Export and Output

**CSV Exporter** (`src/budget_tracker/exporters/csv_exporter.py`):

**Export Method**:
- Writes `StandardTransaction` list to CSV
- Converts Pydantic models to dictionaries
- Creates pandas DataFrame
- Outputs with headers

**Summary Generation** (`src/budget_tracker/exporters/summary.py`):

**Print Summary Function**:
- Groups transactions by category
- Calculates total and count per category
- Displays formatted summary with Rich console
- Shows grand total across all categories

### 8. Configuration Management

**Settings** (`src/budget_tracker/config/settings.py`):

**Paths**:
- `config_dir`: `config/`
- `mappings_file`: `config/bank_mappings.json`
- `categories_file`: `config/categories.yaml`
- `output_dir`: `output/`

**Defaults**:
- `default_output_filename`: "standardized_transactions.csv"
- `default_date_format`: "%d-%m-%Y"

**Ollama Configuration**:
- `ollama_base_url`: "http://localhost:11434"
- `ollama_model`: "llama3.2:3b"

**Methods**:
- `ensure_directories()`: Creates output/config directories if missing
- `load_categories()`: Loads and returns categories from YAML file

**Categories Configuration** (`config/categories.yaml`):
- Defines 11 main categories with subcategories
- Used by LLM categorizer for prompt construction
- Used by confirmation UI for manual category selection

## Code References

### Entry Points and CLI
- `pyproject.toml:34` - Console script registration: `budget-tracker = "budget_tracker.cli.main:app"`
- `src/budget_tracker/cli/main.py:23` - Main `process` command
- `src/budget_tracker/cli/main.py:138` - `list-mappings` command
- `src/budget_tracker/cli/mapping.py:13` - Interactive column mapping
- `src/budget_tracker/cli/confirmation.py:11` - Category confirmation dialog

### Data Models
- `src/budget_tracker/models/transaction.py:12` - StandardTransaction model
- `src/budget_tracker/models/transaction.py:37` - RawTransaction model
- `src/budget_tracker/models/bank_mapping.py:6` - ColumnMapping model
- `src/budget_tracker/models/bank_mapping.py:15` - BankMapping model

### Parsing
- `src/budget_tracker/parsers/csv_parser.py:10` - Encoding detection
- `src/budget_tracker/parsers/csv_parser.py:22` - Delimiter detection
- `src/budget_tracker/parsers/csv_parser.py:37` - CSV parsing
- `src/budget_tracker/parsers/csv_parser.py:56` - Mapping-based loading

### Categorization
- `src/budget_tracker/categorizer/llm_categorizer.py:35` - LLMCategorizer class
- `src/budget_tracker/categorizer/llm_categorizer.py:43` - Categorize method
- `src/budget_tracker/categorizer/llm_categorizer.py:79` - Prompt construction
- `src/budget_tracker/categorizer/llm_categorizer.py:114` - Response parsing

### Normalization & Currency
- `src/budget_tracker/normalizer/transformer.py:15` - Normalize method
- `src/budget_tracker/normalizer/transformer.py:75` - Date parsing
- `src/budget_tracker/normalizer/transformer.py:80` - Amount parsing
- `src/budget_tracker/currency/converter.py:13` - Currency conversion
- `src/budget_tracker/currency/exchange_rate_provider.py:21` - Exchange rate API

### Export
- `src/budget_tracker/exporters/csv_exporter.py` - CSV export implementation
- `src/budget_tracker/exporters/summary.py` - Summary generation

## Architecture Documentation

### Processing Pipeline Flow

```
CSV File(s)
    ↓
[CSV Parser] → auto-detect encoding/delimiter
    ↓
RawTransaction list
    ↓
[LLM Categorizer] → Ollama API
    ↓
CategoryResult list
    ↓
[Transaction Normalizer]
    ├─ Date parsing
    ├─ Amount parsing
    ├─ [Currency Converter] → Frankfurter API → DKK
    └─ StandardTransaction creation
    ↓
StandardTransaction list
    ↓
[User Confirmation] → confidence < 0.6
    ↓
Confirmed StandardTransaction list
    ↓
[CSV Exporter]
    ↓
standardized_transactions.csv + Summary
```

### Design Patterns

**Dependency Injection**:
- `TransactionNormalizer` creates `CurrencyConverter` (`transformer.py:13`)
- `CurrencyConverter` creates `ExchangeRateProvider` (`converter.py:11`)
- Components are composed rather than tightly coupled

**Cache Pattern**:
- Exchange rate provider maintains in-memory cache (`exchange_rate_provider.py:19`)
- Cache key: `(from_currency, to_currency, transaction_date)` tuple
- Prevents duplicate API requests for same currency pairs

**Error Recovery Pattern**:
- LLM categorizer returns fallback result on exceptions (`llm_categorizer.py:66-73`)
- Transaction normalizer returns `None` for invalid transactions (`transformer.py:69-73`)
- CLI filters out `None` results (`main.py:115-116`)

**Validation Chain Pattern**:
- Normalizer validates required fields step by step
- Returns `None` at first validation failure
- Short-circuits unnecessary processing

**Interactive Confirmation Pattern**:
- Filters uncertain results (confidence < 0.6)
- Prompts user for review
- Allows accept/reject/skip per transaction
- Updates confidence to 1.0 for user-confirmed categories

### Data Validation

**Pydantic Models**:
- All data structures use `pydantic.BaseModel`
- Automatic type validation and coercion
- Custom validators for business rules (e.g., non-empty category)

**Field Constraints**:
- `StandardTransaction.confidence`: `Field(default=1.0, ge=0.0, le=1.0)`
- `StandardTransaction.category`: Custom validator ensures non-empty

**Decimal Precision**:
- Uses `decimal.Decimal` for monetary amounts
- Rounds to 2 decimal places with `ROUND_HALF_UP`
- Avoids floating-point precision issues

### External Dependencies

**Required Services**:
1. **Ollama Server** (local LLM):
   - Must be running at `http://localhost:11434`
   - Checked via `utils/ollama.py:4` using `pgrep -f "ollama serve"`
   - Process exits if not running

2. **Frankfurter API** (exchange rates):
   - Public API: `https://api.frankfurter.app`
   - Provides historical ECB exchange rates
   - No authentication required
   - In-memory caching reduces requests

### Test Coverage

**Unit Tests** (`tests/unit/`):
- `test_parser.py` - CSV parsing, delimiter detection, encoding handling
- `test_models.py` - Model validation, field constraints
- `test_normalizer.py` - Data transformation, date/amount parsing
- `test_categorizer.py` - LLM categorization
- `test_currency_converter.py` - Currency conversion, exchange rates
- `test_exporter.py` - CSV export, summary generation

**Integration Tests** (`tests/integration/`):
- `test_end_to_end.py` - Complete pipeline testing

**TDD Approach**:
- Tests written before implementation
- Red-Green-Refactor cycle
- 6-phase implementation plan documented in `.claude/thoughts/plans/`

## Historical Context (from thoughts/)

### Original Vision

**App Idea** (`.claude/thoughts/thoughts/app_idea.md`):
- Purpose: Normalize bank statements from various formats into standardized CSV
- Problem: Each bank has different CSV column names, date formats, currencies
- Solution: Interactive CLI that learns bank formats and categorizes transactions
- Tech Stack: Python, Typer, Rich, Pydantic, pandas, Ollama

### Implementation Plan

**Detailed Plan** (`.claude/thoughts/plans/2025-10-10-bank-statement-normalizer-cli.md`):

**Phase 1: Project Foundation**
- Set up project structure with uv
- Configure pyproject.toml with ruff, mypy, pytest
- Create basic CLI with Typer

**Phase 2: CSV Parser & Column Mapping (TDD)**
- Auto-detect CSV encoding and delimiter
- Interactive column mapping interface
- Persist mappings to JSON

**Phase 3: Data Normalization (TDD)**
- Parse dates with bank-specific formats
- Parse amounts with various decimal separators
- Transform to StandardTransaction model

**Phase 3.5: Currency Conversion (TDD)**
- Integrate Frankfurter API for exchange rates
- Convert all amounts to DKK
- Cache exchange rates in memory

**Phase 4: LLM Categorization (TDD)**
- Integrate Ollama for local LLM
- Build category prompt from YAML
- Parse JSON responses with confidence scores

**Phase 5: Export & Output (TDD)**
- Export to standardized CSV format
- Generate category summary
- Print formatted output with Rich

**Phase 6: CLI Integration & End-to-End Flow**
- Connect all components in main CLI
- Add user confirmation for uncertain categories
- End-to-end integration tests

**Current Status**: Phase 6 completed (per recent commit: "feat: implement Phase 6 - CLI integration & end-to-end flow")

## Related Research

- `.claude/thoughts/thoughts/app_idea.md` - Original application concept and architecture
- `.claude/thoughts/plans/2025-10-10-bank-statement-normalizer-cli.md` - Complete TDD implementation plan

## Key Takeaways

1. **Purpose**: The budget-tracker standardizes bank statement transactions from multiple CSV formats into a unified format with automated categorization.

2. **Core Pipeline**: CSV → Parse → Categorize (LLM) → Normalize (Currency Convert) → Confirm → Export

3. **User Experience**: Interactive CLI that learns bank formats, uses local LLM for categorization, and prompts for uncertain transactions.

4. **Data Quality**: Uses Pydantic for validation, Decimal for precision, confidence scores for uncertainty tracking.

5. **External Dependencies**: Requires local Ollama server for LLM, uses public Frankfurter API for exchange rates.

6. **Test-Driven**: Built using TDD methodology with comprehensive unit and integration tests.

7. **Configuration**: Bank mappings saved to JSON, categories defined in YAML, all paths configurable.

8. **Error Handling**: Graceful fallbacks for LLM failures, skips invalid transactions, validates inputs at each stage.
