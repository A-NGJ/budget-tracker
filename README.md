# Budget Tracker

A CLI tool to standardize bank statements and categorize transactions using a local LLM.

## Features

- Process CSV bank statements from multiple banks
- Automatic transaction categorization using Ollama (local LLM)
- Interactive column mapping for new bank formats
- Currency conversion to DKK
- Export to standardized CSV format

## Requirements

- Python 3.12+
- [Ollama](https://ollama.ai/) running locally

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd budget-tracker

# Install with uv
uv sync
```

## Usage

### Process bank statements

```bash
# Process a single file
budget-tracker process statement.csv --banks mybank

# Process multiple files
budget-tracker process bank1.csv bank2.csv --banks bankA --banks bankB

# Specify output file
budget-tracker process statement.csv --banks mybank --output results.csv
```

### List saved bank mappings

```bash
budget-tracker list-mappings
```

## How It Works

1. **Parse** - Reads CSV files and maps columns to standard fields (date, amount, description)
2. **Categorize** - Uses Ollama to categorize each transaction
3. **Convert** - Converts amounts to DKK
4. **Confirm** - Prompts for review of uncertain categorizations
5. **Export** - Outputs standardized CSV

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
pytest

# Type checking
ty check

# Linting
ruff check

# Formatting
ruff format --check
```

## Project Structure

```
src/budget_tracker/
├── cli/           # Command-line interface
├── categorizer/   # LLM categorization
├── config/        # Settings and configuration
├── currency/      # Currency conversion
├── exporters/     # Output formatters
├── models/        # Data models
├── parsers/       # CSV parsing
└── utils/         # Utilities
```
