---
date: 2026-01-02T00:00:00+01:00
researcher: Claude
git_commit: efe90af220f6f471ebef95a746c5bc0d9eec9af9
branch: main
repository: budget-tracker
topic: "Google Sheets Integration for Bank Statement Output"
tags: [research, codebase, google-sheets, export, integration]
status: complete
last_updated: 2026-01-02
last_updated_by: Claude
---

# Research: Google Sheets Integration for Bank Statement Output

**Date**: 2026-01-02
**Researcher**: Claude
**Git Commit**: efe90af220f6f471ebef95a746c5bc0d9eec9af9
**Branch**: main
**Repository**: budget-tracker

## Research Question

Understanding the current codebase architecture to add Google Sheets integration for outputting bank statements.

## Summary

The budget tracker currently exports standardized transactions exclusively to CSV files. The export system uses a simple pattern: `CSVExporter` receives a list of `StandardTransaction` objects and writes them to a file. There is no exporter abstraction layer (interface/protocol), and no other output formats are currently implemented.

Key architectural observations:
- **Data Model**: `StandardTransaction` (Pydantic model) with 7 fields
- **Export Pattern**: Direct exporter instantiation in CLI, no factory/strategy pattern
- **Existing Integrations**: Ollama (local LLM) and Frankfurter API (exchange rates) - both unauthenticated
- **No Google Services**: No existing Google API integration or OAuth implementation

## Detailed Findings

### Data Model: StandardTransaction

**File:** `src/budget_tracker/models/transaction.py:12-74`

The core data structure for exported transactions:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | `datetime.date` | Yes | Transaction date |
| `category` | `str` | Yes | Validated against categories.yaml |
| `subcategory` | `str \| None` | No | Validated under parent category |
| `amount` | `Decimal` | Yes | Amount in DKK |
| `source` | `str` | Yes | Bank identifier |
| `description` | `str \| None` | No | Original description |
| `confidence` | `float` | No | LLM confidence (0.0-1.0), default 1.0 |

**Note:** The `confidence` field is NOT exported to CSV (it's internal metadata).

### Current Export Implementation

**File:** `src/budget_tracker/exporters/csv_exporter.py:9-51`

```python
class CSVExporter:
    def __init__(self, settings: Settings, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, transactions: list[StandardTransaction], output_file: Path) -> Path:
        # Transforms transactions to dicts, creates DataFrame, sorts, writes CSV
        ...
```

**Export column mapping:**
- `t.date` → `"Date"` (formatted as `"%Y-%m-%d"`)
- `t.description` → `"Description"`
- `t.category` → `"Category"`
- `t.subcategory` → `"Subcategory"`
- `t.amount` → `"Amount (DKK)"` (converted to float)
- `t.source` → `"Source"`

**Column order:** Date, Description, Category, Subcategory, Amount (DKK), Source

### CLI Integration

**File:** `src/budget_tracker/cli/main.py:157-163`

```python
# Step 5: Export
output_file = output or (settings.output_dir / settings.default_output_filename)
exporter = CSVExporter(_settings)
result_file = exporter.export(standardized, output_file)
```

**Current CLI options:**
- `--output` / `-o`: Optional output CSV file path
- Default output: `data/output/standardized_transactions.csv`

**No format selection option exists** - CSV is hardcoded.

### Existing External Integrations

| Service | Type | Authentication | Files |
|---------|------|----------------|-------|
| Ollama | Local LLM | None (local) | `categorizer/llm_categorizer.py`, `utils/ollama.py` |
| Frankfurter API | Exchange rates | None (public API) | `currency/exchange_rate_provider.py` |

**Key observation:** No OAuth, no credential storage, no authenticated external services currently exist.

### Package Dependencies

**File:** `pyproject.toml`

Current HTTP/API dependencies:
- `httpx` - Used for Frankfurter API calls
- `ollama>=0.3.0` - Ollama Python client
- `pandas` - Data manipulation (used in CSV export)

No Google-related packages currently installed.

### Directory Structure for Exporters

```
src/budget_tracker/exporters/
├── __init__.py          # Empty
├── csv_exporter.py      # CSVExporter class
└── summary.py           # print_summary() for console output
```

### Configuration System

**File:** `src/budget_tracker/config/settings.py:11-38`

Uses `pydantic_settings.BaseSettings` for configuration:

```python
class Settings(BaseSettings):
    output_dir: Path = Path.cwd() / "data" / "output"
    default_output_filename: str = "standardized_transactions.csv"
    # ... other settings
```

Environment variables can override settings (standard pydantic-settings behavior).

## Code References

- `src/budget_tracker/models/transaction.py:12-74` - StandardTransaction model
- `src/budget_tracker/exporters/csv_exporter.py:9-51` - CSVExporter implementation
- `src/budget_tracker/cli/main.py:157-163` - Export invocation in CLI
- `src/budget_tracker/cli/main.py:51-53` - Output CLI option definition
- `src/budget_tracker/config/settings.py:11-38` - Settings class
- `src/budget_tracker/currency/exchange_rate_provider.py` - Example of HTTP API integration

## Architecture Documentation

### Current Export Pattern

```
CLI (main.py)
    │
    ├── Resolves output path
    ├── Instantiates CSVExporter(settings)
    └── Calls exporter.export(transactions, output_file)
            │
            └── CSVExporter
                    │
                    ├── Transforms StandardTransaction → dict
                    ├── Creates pandas DataFrame
                    ├── Sorts by date
                    └── Writes to CSV file
```

### No Abstraction Layer

The `exporters/__init__.py` is empty - there is no:
- Base exporter class
- Exporter protocol/interface
- Factory for creating exporters
- Format selection mechanism

### Data Flow

```
Bank CSVs → Parser → ParsedTransaction → Categorizer → StandardTransaction → CSVExporter → CSV File
```

## Historical Context (from thoughts/)

### Original App Idea

**File:** `.claude/thoughts/thoughts/app_idea.md`

- Output was always intended to be CSV only
- Privacy-first architecture: local LLM, no cloud services
- CLI-only interface
- File-based storage only

### Implementation Plan

**File:** `.claude/thoughts/plans/2025-10-10-bank-statement-normalizer-cli.md`

- Google Sheets was NOT part of the original plan
- Future enhancements mentioned "Excel, JSON" but not Google Sheets
- Explicitly out of scope: cloud-based services, web interface

## Related Research

- `.claude/thoughts/shared/research/2026-01-02-bank-mapping-config-format-extension.md` - Bank mapping configuration research
- `.claude/thoughts/shared/plans/2026-01-02-bank-mapping-yaml-migration.md` - Recent YAML migration plan

## Open Questions

1. **Authentication Strategy**: How should Google OAuth credentials be stored and managed? (Environment variables vs credential file vs interactive flow)
Interactive flow that saves credentials locally with TTL.
2. **Spreadsheet Targeting**: Should it create new spreadsheets or append to existing ones?
It should use one sheet per year. If one exists it should be appended. There should be some kind of unique ID for each transaction (e.g. hashed values date + amount + something) to keep track of which transactions are already added to the spreadseet.
3. **CLI Interface**: New flag on `process` command (`--sheets`) or separate `export-sheets` command?
New flag.
4. **Privacy Considerations**: Original design was privacy-first with local processing - does cloud export align with project goals?
Yes.
5. **Exporter Abstraction**: Should an exporter interface/protocol be introduced, or just add Google Sheets exporter alongside CSV?
Yes, an exporter interface/protocol should be introduced to allow for future extensibility.
