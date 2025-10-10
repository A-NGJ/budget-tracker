# Bank Statement Normalizer CLI Implementation Plan

## Overview

Build a privacy-focused CLI application that standardizes arbitrary bank statement CSVs into a unified format with intelligent transaction categorization using local LLM. The app will handle multiple bank formats, provide interactive column mapping, and combine multiple files into a single standardized output.

## Current State Analysis

**What exists:**

- Fresh Python 3.14 project (`pyproject.toml` configured)
- Basic `main.py` with placeholder function
- Git repository initialized

**What's missing:**

- Entire application architecture and modules
- Dependency configuration
- Test infrastructure
- Data schemas and models
- CLI interface
- LLM integration

### Key Requirements:

- Privacy-first: Local LLM via Ollama (Llama 3.2 1B/3B)
- Handle arbitrary CSV formats from different banks
- Interactive column mapping with saved configurations
- Fixed category system from YAML file
- Multi-file processing with combined output
- TDD approach throughout development

## Desired End State

A production-ready CLI tool that:

- Accepts one or more bank statement CSV files as input
- Interactively maps columns on first use per bank
- Categorizes transactions using local LLM with user confirmation for uncertain cases
- Outputs standardized CSV: Date, Category, Amount (DKK), Source
- Saves bank mappings for reuse
- Handles malformed data gracefully

### Verification:

```bash
# User can run:
budget-tracker process bank1.csv bank2.csv --output results.csv

# Output: Standardized CSV with all transactions categorized
# Verification: Manual inspection + unit/integration tests passing
```

## What We're NOT Doing

- Cloud-based LLM APIs (privacy requirement)
- Web interface or GUI
- Database storage (file-based only)
- Real-time bank API integrations
- Transaction deduplication (out of scope for v1)
- Budget tracking or analytics features

## Implementation Approach

Following TDD (Test-Driven Development) methodology:

1. Write failing tests first for each component
2. Implement minimal code to pass tests
3. Refactor while keeping tests green
4. Build incrementally from core data models outward

**Code Quality Standards:**

- **ALL code MUST be fully type annotated** (Python 3.14 type hints)
- **ALL code MUST pass `ruff` linting** with zero errors/warnings
- **ALL code MUST pass `mypy` strict type checking** with zero errors
- Follow PEP 8 style guidelines
- Maximum line length: 100 characters
- Use descriptive variable and function names

Tech stack execution:

- **Typer** for modern CLI with type hints
- **Pydantic** for data validation and settings
- **Pandas** for CSV manipulation
- **Ollama Python client** for LLM integration
- **PyYAML** for category configuration
- **httpx** for exchange rate API calls
- **pytest** for testing

---

## Phase 1: Project Foundation & Core Structure

### Overview

Set up the project architecture, dependencies, and core data models with comprehensive test coverage following TDD principles.

### Changes Required:

#### 1. Project Structure

**Create directories:**

```
budget-tracker/
├── src/
│   └── budget_tracker/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── transaction.py
│       │   └── bank_mapping.py
│       ├── parsers/
│       │   ├── __init__.py
│       │   └── csv_parser.py
│       ├── categorizer/
│       │   ├── __init__.py
│       │   └── llm_categorizer.py
│       ├── currency/
│       │   ├── __init__.py
│       │   ├── exchange_rate_provider.py
│       │   └── converter.py
│       ├── exporters/
│       │   ├── __init__.py
│       │   └── csv_exporter.py
│       └── config/
│           ├── __init__.py
│           └── settings.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_models.py
│   │   ├── test_parser.py
│   │   ├── test_categorizer.py
│   │   ├── test_currency_converter.py
│   │   └── test_exporter.py
│   ├── integration/
│   │   └── test_end_to_end.py
│   └── fixtures/
│       ├── sample_bank1.csv
│       └── sample_bank2.csv
├── config/
│   ├── categories.yaml
│   └── bank_mappings.json
├── data/
│   └── output/
├── pyproject.toml
├── README.md
└── main.py (to be refactored)
```

#### 2. Update Dependencies

**File**: `pyproject.toml`

```toml
[project]
name = "budget-tracker"
version = "0.1.0"
description = "CLI tool to standardize bank statements with local LLM categorization"
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "typer[all]>=0.12.0",
    "pandas>=2.2.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.3.0",
    "ollama>=0.3.0",
    "pyyaml>=6.0.1",
    "rich>=13.7.0",  # for beautiful CLI output
    "httpx>=0.27.0",  # for exchange rate API calls
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
    "pandas-stubs>=2.2.0",
]

[project.scripts]
budget-tracker = "budget_tracker.cli.main:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.ruff]
line-length = 100
target-version = "py314"
select = ["E", "F", "I", "N", "W", "UP", "ANN", "B", "C4", "DTZ", "T10", "EM", "ISC", "ICN", "G", "PIE", "PYI", "Q", "SIM", "TCH", "ARG", "PTH", "PD", "PL", "RUF"]
ignore = ["ANN101", "ANN102"]  # Ignore missing type annotations for self and cls

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.14"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_unimported = false
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
check_untyped_defs = true
strict_equality = true
```

#### 3. Core Data Models (TDD)

**File**: `tests/unit/test_models.py`
**Changes**: Write tests first

```python
import pytest
from datetime import date
from decimal import Decimal
from budget_tracker.models.transaction import StandardTransaction, RawTransaction
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


class TestStandardTransaction:
    def test_create_valid_transaction(self):
        """Test creating a valid standardized transaction"""
        transaction = StandardTransaction(
            date=date(2025, 10, 10),
            category="Food & Dining",
            subcategory="Restaurants",
            amount=Decimal("125.50"),
            source="Danske Bank"
        )
        assert transaction.date == date(2025, 10, 10)
        assert transaction.amount == Decimal("125.50")
        assert transaction.category == "Food & Dining"

    def test_negative_amount_validation(self):
        """Test that expenses are stored as negative amounts"""
        transaction = StandardTransaction(
            date=date(2025, 10, 10),
            category="Food & Dining",
            subcategory="Restaurants",
            amount=Decimal("-125.50"),
            source="Danske Bank"
        )
        assert transaction.amount < 0

    def test_invalid_category_raises_error(self):
        """Test that invalid category raises validation error"""
        with pytest.raises(ValueError):
            StandardTransaction(
                date=date(2025, 10, 10),
                category="InvalidCategory",
                subcategory="Test",
                amount=Decimal("100"),
                source="Test Bank"
            )


class TestRawTransaction:
    def test_create_raw_transaction(self):
        """Test creating raw transaction from CSV data"""
        raw = RawTransaction(
            data={"Date": "10-10-2025", "Amount": "125.50", "Description": "Cafe"},
            source_file="bank1.csv"
        )
        assert raw.data["Date"] == "10-10-2025"
        assert raw.source_file == "bank1.csv"


class TestBankMapping:
    def test_create_bank_mapping(self):
        """Test creating bank column mapping configuration"""
        mapping = BankMapping(
            bank_name="Danske Bank",
            column_mapping=ColumnMapping(
                date_column="Dato",
                amount_column="Beløb",
                description_column="Tekst"
            ),
            date_format="%d-%m-%Y"
        )
        assert mapping.bank_name == "Danske Bank"
        assert mapping.column_mapping.date_column == "Dato"

    def test_to_dict_serialization(self):
        """Test serializing mapping to dict for JSON storage"""
        mapping = BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_column="Desc"
            ),
            date_format="%Y-%m-%d"
        )
        data = mapping.model_dump()
        assert data["bank_name"] == "Test Bank"
        assert data["date_format"] == "%Y-%m-%d"
```

**File**: `src/budget_tracker/models/transaction.py`
**Changes**: Implement models to pass tests

```python
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional


class StandardTransaction(BaseModel):
    """Standardized transaction format"""
    date: date
    category: str
    subcategory: Optional[str] = None
    amount: Decimal
    source: str  # Bank name
    description: Optional[str] = None  # Original description
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: str) -> str:
        # Will be validated against categories.yaml in later phase
        # For now, just ensure it's not empty
        if not v or not v.strip():
            raise ValueError("Category cannot be empty")
        return v

    class Config:
        frozen = False  # Allow modifications for LLM categorization


class RawTransaction(BaseModel):
    """Raw transaction data from CSV before normalization"""
    data: Dict[str, Any]
    source_file: str
    row_number: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True
```

**File**: `src/budget_tracker/models/bank_mapping.py`
**Changes**: Implement bank mapping models

```python
from pydantic import BaseModel
from typing import Optional


class ColumnMapping(BaseModel):
    """Maps CSV columns to standard fields"""
    date_column: str
    amount_column: str
    description_column: str
    currency_column: Optional[str] = None  # Optional: if currency is in a column


class BankMapping(BaseModel):
    """Saved configuration for a specific bank's CSV format"""
    bank_name: str
    column_mapping: ColumnMapping
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    default_currency: str = "DKK"  # Default currency if not specified per transaction

    class Config:
        frozen = False
```

#### 4. Categories Configuration

**File**: `config/categories.yaml`
**Changes**: Create category taxonomy

```yaml
categories:
  - name: "Food & Drinks"
    subcategories:
      - "Groceries"
      - "Restaurants"
      - "Coffee & Cafes"
      - "Other"

  - name: "Shopping"
    subcategories:
      - "Clothing"
      - "Electronics"
      - "Home Goods"
      - "Personal Care"
      - "Sport"
      - "Other hobbies"
      - "Tools"
      - "Other"

  - name: "Housing"
    subcategories:
      - "Rent"
      - "Internet"
      - "Electricity"
      - "Heating"
      - "Water"
      - "Other"

  - name: "Transportation"
    subcategories:
      - "Public Transport"
      - "Taxi & Rideshare"
      - "Bicycle"
      - "Other"

  - name: "Car"
    subcategories:
      - "Fuel"
      - "Maintenance"
      - "Insurance"
      - "Parking"
      - "Other"

  - name: "Life & Entertainment"
    subcategories:
      - "Streaming Services"
      - "Events & Activities"
      - "Hobbies"
      - "Holiday, Trips, Hotels"
      - "Flights"
      - "Active Sport"
      - "Culture & Sport Events"
      - "Other"

  - name: "Healthcare"
    subcategories:
      - "Medicine"
      - "Doctor & Dentist"
      - "Health Insurance"
      - "Other"

  - name: "Communication & PC"
    subcategories:
      - "Mobile"
      - "Software, Apps, Games"
      - "Other"

  - name: "Financial expenses"
    subcategories:
      - "Bank Fees"
      - "Insurance"
      - "Loans & Credits"
      - "Other"

  - name: "Investments"
    subcategories:
      - "Investments"

  - name: "Income"
    subcategories:
      - "Salary"
      - "Investment Return"
      - "Sales"
      - "Other"

  - name: "Other"
    subcategories:
        - "Uncategorized"
```

#### 5. Settings and Configuration Management

**File**: `src/budget_tracker/config/settings.py`
**Changes**: Create settings model

```python
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List, Dict
import yaml


class Settings(BaseSettings):
    """Application settings"""
    config_dir: Path = Path.cwd() / "config"
    data_dir: Path = Path.cwd() / "data"
    output_dir: Path = Path.cwd() / "data" / "output"

    categories_file: Path = Path.cwd() / "config" / "categories.yaml"
    mappings_file: Path = Path.cwd() / "config" / "bank_mappings.json"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    default_output_filename: str = "standardized_transactions.csv"
    default_date_format: str = "%d-%m-%Y"  # DD-MM-YYYY format

    def load_categories(self) -> Dict:
        """Load categories from YAML file"""
        with open(self.categories_file, 'r') as f:
            return yaml.safe_load(f)

    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
```

#### 6. Quality Check Script

**File**: `scripts/check_quality.sh`
**Changes**: Create script to run all quality checks

```bash
#!/bin/bash
set -e

echo "🔍 Running code quality checks..."

echo ""
echo "1️⃣  Running ruff linting..."
ruff check src/ tests/

echo ""
echo "2️⃣  Checking code formatting..."
ruff format src/ tests/ --check

echo ""
echo "3️⃣  Running mypy type checking..."
mypy src/ --strict

echo ""
echo "4️⃣  Running tests..."
pytest tests/ -v

echo ""
echo "✅ All quality checks passed!"
```

Make executable: `chmod +x scripts/check_quality.sh`

### Success Criteria:

#### Automated Verification:

- [x] Project structure created successfully
- [x] Dependencies install without errors: `uv sync --group dev`
- [x] All model tests pass: `pytest tests/unit/test_models.py -v`
- [x] **Type checking passes with strict mode: `mypy src/ --strict`**
- [x] **Linting passes with zero errors: `ruff check src/`**
- [x] **Code formatting is correct: `ruff format src/ --check`**
- [ ] **Quality check script runs successfully: `./scripts/check_quality.sh`**
- [x] Can import models: `python -c "from budget_tracker.models.transaction import StandardTransaction"`

#### Manual Verification:

- [x] Directory structure matches specification
- [x] `categories.yaml` is readable and well-structured
- [x] Settings can load configuration files without errors

---

## Phase 2: CSV Parser & Column Mapping (TDD)

### Overview

Implement CSV parsing, format detection, and interactive column mapping with persistent storage of bank configurations.

### Changes Required:

#### 1. Parser Tests

**File**: `tests/unit/test_parser.py`
**Changes**: Write comprehensive parser tests

```python
import pytest
import pandas as pd
from pathlib import Path
from budget_tracker.parsers.csv_parser import CSVParser, detect_delimiter
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


class TestCSVParser:
    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a sample CSV file for testing"""
        csv_content = """Dato,Beløb,Tekst
10-10-2025,125.50,Cafe X
11-10-2025,-50.00,Supermarket"""
        csv_file = tmp_path / "test_bank.csv"
        csv_file.write_text(csv_content)
        return csv_file

    def test_detect_delimiter_comma(self, sample_csv):
        """Test delimiter detection for comma-separated files"""
        delimiter = detect_delimiter(sample_csv)
        assert delimiter == ","

    def test_detect_delimiter_semicolon(self, tmp_path):
        """Test delimiter detection for semicolon-separated files"""
        csv_content = """Date;Amount;Description
2025-10-10;125.50;Purchase"""
        csv_file = tmp_path / "semicolon.csv"
        csv_file.write_text(csv_content)
        delimiter = detect_delimiter(csv_file)
        assert delimiter == ";"

    def test_parse_csv_without_mapping(self, sample_csv):
        """Test parsing CSV and detecting columns"""
        parser = CSVParser()
        df, columns = parser.parse_file(sample_csv)
        assert len(df) == 2
        assert "Dato" in columns
        assert "Beløb" in columns
        assert "Tekst" in columns

    def test_load_with_mapping(self, sample_csv):
        """Test loading CSV with pre-configured mapping"""
        mapping = BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Dato",
                amount_column="Beløb",
                description_column="Tekst"
            ),
            date_format="%d-%m-%Y"
        )
        parser = CSVParser()
        raw_transactions = parser.load_with_mapping(sample_csv, mapping)
        assert len(raw_transactions) == 2
        assert raw_transactions[0].data["Dato"] == "10-10-2025"

    def test_handle_malformed_csv(self, tmp_path):
        """Test graceful handling of malformed CSV"""
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("not,a,proper\ncsv,file")
        parser = CSVParser()
        df, columns = parser.parse_file(bad_csv)
        assert df is not None  # Should not crash


class TestInteractiveMapping:
    def test_create_mapping_from_user_input(self):
        """Test creating mapping from simulated user selections"""
        # This will be implemented with Typer prompts
        pass
```

**File**: `src/budget_tracker/parsers/csv_parser.py`
**Changes**: Implement CSV parser

```python
import csv
import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional
from budget_tracker.models.transaction import RawTransaction
from budget_tracker.models.bank_mapping import BankMapping


def detect_delimiter(file_path: Path) -> str:
    """Detect CSV delimiter by analyzing first few lines"""
    with open(file_path, 'r', encoding='utf-8') as f:
        sample = f.read(1024)
        sniffer = csv.Sniffer()
        try:
            delimiter = sniffer.sniff(sample).delimiter
            return delimiter
        except csv.Error:
            return ','  # Default to comma


class CSVParser:
    """Parse bank statement CSV files"""

    def parse_file(self, file_path: Path) -> Tuple[pd.DataFrame, List[str]]:
        """
        Parse CSV file and return DataFrame with detected columns.

        Returns:
            Tuple of (DataFrame, list of column names)
        """
        delimiter = detect_delimiter(file_path)
        try:
            df = pd.read_csv(file_path, delimiter=delimiter, dtype=str)
            # Strip whitespace from column names
            df.columns = df.columns.str.strip()
            return df, df.columns.tolist()
        except Exception as e:
            raise ValueError(f"Failed to parse CSV: {e}")

    def load_with_mapping(
        self,
        file_path: Path,
        mapping: BankMapping
    ) -> List[RawTransaction]:
        """
        Load CSV using a pre-configured bank mapping.

        Returns:
            List of RawTransaction objects
        """
        df, _ = self.parse_file(file_path)

        transactions = []
        for idx, row in df.iterrows():
            # Skip rows with missing critical data
            if pd.isna(row.get(mapping.column_mapping.date_column)) or \
               pd.isna(row.get(mapping.column_mapping.amount_column)):
                continue

            transactions.append(RawTransaction(
                data=row.to_dict(),
                source_file=str(file_path),
                row_number=idx
            ))

        return transactions
```

#### 2. Interactive Mapping CLI

**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Create interactive mapping interface

```python
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.prompt import Prompt
from budget_tracker.parsers.csv_parser import CSVParser
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping
from budget_tracker.config.settings import settings
import json

console = Console()


def interactive_column_mapping(
    file_path: Path,
    available_columns: List[str]
) -> Optional[BankMapping]:
    """
    Guide user through interactive column mapping.

    Returns:
        BankMapping if successful, None if cancelled
    """
    console.print("\n[bold]Column Mapping Setup[/bold]")
    console.print(f"Available columns in CSV: {', '.join(available_columns)}\n")

    # Bank name
    bank_name = Prompt.ask(
        "Enter bank name (e.g., 'Danske Bank', 'Nordea')",
        default=file_path.stem
    )

    # Date column
    date_col = Prompt.ask(
        "Which column contains the transaction date?",
        choices=available_columns
    )

    # Amount column
    amount_col = Prompt.ask(
        "Which column contains the amount?",
        choices=available_columns
    )

    # Description column
    desc_col = Prompt.ask(
        "Which column contains the description/text?",
        choices=available_columns
    )

    # Date format - use default from settings
    date_format = settings.default_date_format
    console.print(f"\n[dim]Using date format: DD-MM-YYYY[/dim]")

    # Create mapping
    mapping = BankMapping(
        bank_name=bank_name,
        column_mapping=ColumnMapping(
            date_column=date_col,
            amount_column=amount_col,
            description_column=desc_col
        ),
        date_format=date_format
    )

    # Confirm
    console.print("\n[bold green]Mapping created:[/bold green]")
    console.print(f"  Bank: {bank_name}")
    console.print(f"  Date: {date_col} (format: {date_format})")
    console.print(f"  Amount: {amount_col}")
    console.print(f"  Description: {desc_col}")

    save = Prompt.ask("\nSave this mapping?", choices=["y", "n"], default="y")

    if save == "y":
        return mapping
    return None


def save_mapping(mapping: BankMapping, mappings_file: Path):
    """Save bank mapping to JSON file"""
    mappings = {}
    if mappings_file.exists():
        with open(mappings_file, 'r') as f:
            mappings = json.load(f)

    mappings[mapping.bank_name] = mapping.model_dump()

    with open(mappings_file, 'w') as f:
        json.dump(mappings, f, indent=2)

    console.print(f"[green]✓[/green] Mapping saved for {mapping.bank_name}")


def load_mapping(bank_name: str, mappings_file: Path) -> Optional[BankMapping]:
    """Load saved bank mapping by name"""
    if not mappings_file.exists():
        return None

    with open(mappings_file, 'r') as f:
        mappings = json.load(f)

    if bank_name in mappings:
        return BankMapping(**mappings[bank_name])
    return None
```

#### 3. Multiple File Handling

**File**: `src/budget_tracker/parsers/multi_file.py`
**Changes**: Handle multiple input files

```python
from pathlib import Path
from typing import List
from budget_tracker.models.transaction import RawTransaction
from budget_tracker.parsers.csv_parser import CSVParser
from budget_tracker.models.bank_mapping import BankMapping


class MultiFileProcessor:
    """Process multiple CSV files and combine results"""

    def __init__(self):
        self.parser = CSVParser()

    def process_files(
        self,
        file_paths: List[Path],
        mappings: dict[str, BankMapping]
    ) -> List[RawTransaction]:
        """
        Process multiple CSV files and return combined raw transactions.

        Args:
            file_paths: List of CSV files to process
            mappings: Dict of bank_name -> BankMapping

        Returns:
            Combined list of RawTransaction objects
        """
        all_transactions = []

        for file_path in file_paths:
            # Try to find matching mapping by filename or bank name
            mapping = self._find_mapping_for_file(file_path, mappings)

            if mapping:
                transactions = self.parser.load_with_mapping(file_path, mapping)
                all_transactions.extend(transactions)
            else:
                # Will need interactive mapping in CLI flow
                raise ValueError(f"No mapping found for {file_path.name}")

        return all_transactions

    def _find_mapping_for_file(
        self,
        file_path: Path,
        mappings: dict[str, BankMapping]
    ) -> BankMapping | None:
        """Try to match file to a saved bank mapping"""
        # Try exact match on filename stem
        for bank_name, mapping in mappings.items():
            if bank_name.lower() in file_path.stem.lower():
                return mapping
        return None
```

### Success Criteria:

#### Automated Verification:

- [ ] All parser tests pass: `pytest tests/unit/test_parser.py -v`
- [ ] CSV files can be parsed: Test with sample CSVs
- [ ] Mappings save/load correctly: Verify JSON serialization
- [ ] **Type checking passes with strict mode: `mypy src/budget_tracker/parsers/ --strict`**
- [ ] **Linting passes with zero errors: `ruff check src/budget_tracker/parsers/`**
- [ ] Delimiter detection works for comma and semicolon

#### Manual Verification:

- [ ] Interactive mapping flow works smoothly in CLI
- [ ] Can process multiple files with different formats
- [ ] Saved mappings persist between runs
- [ ] Error messages are clear for malformed CSVs

---

## Phase 3: Data Normalization (TDD)

### Overview

Transform raw CSV data into standardized transaction format with proper date/amount parsing and validation.

### Changes Required:

#### 1. Normalizer Tests

**File**: `tests/unit/test_normalizer.py`
**Changes**: Write normalization tests

# BOOKMARK:
```python
import pytest
from datetime import date
from decimal import Decimal
from budget_tracker.normalizer.transformer import TransactionNormalizer
from budget_tracker.models.transaction import RawTransaction, StandardTransaction
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


class TestTransactionNormalizer:
    @pytest.fixture
    def normalizer(self):
        return TransactionNormalizer()

    @pytest.fixture
    def sample_mapping(self):
        return BankMapping(
            bank_name="Test Bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_column="Description"
            ),
            date_format="%d-%m-%Y"
        )

    def test_normalize_simple_transaction(self, normalizer, sample_mapping):
        """Test normalizing a basic transaction"""
        raw = RawTransaction(
            data={
                "Date": "10-10-2025",
                "Amount": "-125.50",
                "Description": "Cafe Purchase"
            },
            source_file="test.csv"
        )

        # Category will be set by LLM, for now use placeholder
        standard = normalizer.normalize(raw, sample_mapping, category="Food & Dining")

        assert standard.date == date(2025, 10, 10)
        assert standard.amount == Decimal("-125.50")
        assert standard.source == "Test Bank"
        assert standard.description == "Cafe Purchase"

    def test_parse_various_date_formats(self, normalizer, sample_mapping):
        """Test parsing different date formats"""
        test_cases = [
            ("10-10-2025", "%d-%m-%Y", date(2025, 10, 10)),
            ("2025-10-10", "%Y-%m-%d", date(2025, 10, 10)),
            ("10/10/2025", "%d/%m/%Y", date(2025, 10, 10)),
        ]

        for date_str, format_str, expected in test_cases:
            sample_mapping.date_format = format_str
            raw = RawTransaction(
                data={"Date": date_str, "Amount": "100", "Description": "Test"},
                source_file="test.csv"
            )
            standard = normalizer.normalize(raw, sample_mapping, category="Other")
            assert standard.date == expected

    def test_parse_amount_with_different_separators(self, normalizer, sample_mapping):
        """Test parsing amounts with comma/dot separators"""
        test_cases = [
            ("1234.56", ".", Decimal("1234.56")),
            ("1234,56", ",", Decimal("1234.56")),
            ("-1234.56", ".", Decimal("-1234.56")),
        ]

        for amount_str, separator, expected in test_cases:
            sample_mapping.decimal_separator = separator
            raw = RawTransaction(
                data={"Date": "10-10-2025", "Amount": amount_str, "Description": "Test"},
                source_file="test.csv"
            )
            standard = normalizer.normalize(raw, sample_mapping, category="Other")
            assert standard.amount == expected

    def test_handle_missing_optional_fields(self, normalizer, sample_mapping):
        """Test graceful handling of missing data"""
        raw = RawTransaction(
            data={"Date": "10-10-2025", "Amount": "100", "Description": ""},
            source_file="test.csv"
        )
        standard = normalizer.normalize(raw, sample_mapping, category="Other")
        assert standard.description == "" or standard.description is None

    def test_skip_invalid_transactions(self, normalizer, sample_mapping):
        """Test that malformed transactions return None"""
        raw = RawTransaction(
            data={"Date": "invalid-date", "Amount": "100", "Description": "Test"},
            source_file="test.csv"
        )
        result = normalizer.normalize(raw, sample_mapping, category="Other")
        assert result is None  # Should skip invalid data
```

**File**: `src/budget_tracker/normalizer/transformer.py`
**Changes**: Implement normalization logic

```python
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional
from budget_tracker.models.transaction import RawTransaction, StandardTransaction
from budget_tracker.models.bank_mapping import BankMapping


class TransactionNormalizer:
    """Transform raw CSV data into standardized format"""

    def normalize(
        self,
        raw: RawTransaction,
        mapping: BankMapping,
        category: str,
        subcategory: Optional[str] = None,
        confidence: float = 1.0
    ) -> Optional[StandardTransaction]:
        """
        Normalize a raw transaction to standard format.

        Returns None if transaction is invalid and should be skipped.
        """
        try:
            # Parse date
            date_str = raw.data.get(mapping.column_mapping.date_column)
            if not date_str:
                return None
            parsed_date = self._parse_date(date_str, mapping.date_format)

            # Parse amount
            amount_str = raw.data.get(mapping.column_mapping.amount_column)
            if not amount_str:
                return None
            amount = self._parse_amount(amount_str, mapping.decimal_separator)

            # Determine currency
            if mapping.column_mapping.currency_column:
                currency = raw.data.get(mapping.column_mapping.currency_column, mapping.default_currency)
            else:
                currency = mapping.default_currency

            # Convert to DKK if needed (will be done in Phase 3.5)
            # For now, store original amount
            # TODO: Integrate currency converter in Phase 3.5

            # Get description
            description = raw.data.get(mapping.column_mapping.description_column, "")

            return StandardTransaction(
                date=parsed_date,
                category=category,
                subcategory=subcategory,
                amount=amount,
                source=mapping.bank_name,
                description=description,
                confidence=confidence
            )
        except (ValueError, InvalidOperation) as e:
            # Log error and skip malformed transaction
            return None

    def _parse_date(self, date_str: str, date_format: str) -> date:
        """Parse date string according to format"""
        return datetime.strptime(date_str.strip(), date_format).date()

    def _parse_amount(self, amount_str: str, decimal_separator: str) -> Decimal:
        """Parse amount string handling different decimal separators"""
        # Remove whitespace and thousand separators
        clean_amount = amount_str.strip().replace(" ", "").replace("'", "")

        # Handle comma as decimal separator
        if decimal_separator == ",":
            clean_amount = clean_amount.replace(".", "").replace(",", ".")
        else:
            clean_amount = clean_amount.replace(",", "")

        return Decimal(clean_amount)
```

#### 2. Batch Normalization

**File**: `src/budget_tracker/normalizer/batch_processor.py`
**Changes**: Process multiple transactions

```python
from typing import List
from budget_tracker.models.transaction import RawTransaction, StandardTransaction
from budget_tracker.models.bank_mapping import BankMapping
from budget_tracker.normalizer.transformer import TransactionNormalizer


class BatchNormalizer:
    """Normalize batches of transactions"""

    def __init__(self):
        self.normalizer = TransactionNormalizer()

    def normalize_batch(
        self,
        raw_transactions: List[RawTransaction],
        mapping: BankMapping,
        categories: dict  # Will come from LLM in next phase
    ) -> List[StandardTransaction]:
        """
        Normalize a batch of raw transactions.

        Args:
            raw_transactions: List of raw transactions
            mapping: Bank mapping configuration
            categories: Dict mapping transaction description to category

        Returns:
            List of successfully normalized transactions
        """
        normalized = []

        for raw in raw_transactions:
            # Get category from pre-categorized dict
            # In next phase, this will call LLM
            category = categories.get(raw.data.get(mapping.column_mapping.description_column), "Other")

            standard = self.normalizer.normalize(raw, mapping, category)
            if standard:
                normalized.append(standard)

        return normalized
```

### Success Criteria:

#### Automated Verification:

- [ ] All normalizer tests pass: `pytest tests/unit/test_normalizer.py -v`
- [ ] Date parsing handles multiple formats correctly
- [ ] Amount parsing handles comma and dot decimal separators
- [ ] Invalid transactions are skipped gracefully
- [ ] **Type checking passes with strict mode: `mypy src/budget_tracker/normalizer/ --strict`**
- [ ] **Linting passes with zero errors: `ruff check src/budget_tracker/normalizer/`**

#### Manual Verification:

- [ ] Test with real bank statements from different banks
- [ ] Verify correct handling of positive/negative amounts
- [ ] Check edge cases: empty descriptions, unusual formats

---

## Phase 3.5: Currency Conversion (TDD)

### Overview

Implement automatic currency conversion to DKK using historical exchange rates from the transaction date. Integrate with a free exchange rate API (Frankfurter API) to fetch rates.

### Changes Required:

#### 1. Currency Converter Tests

**File**: `tests/unit/test_currency_converter.py`
**Changes**: Write currency conversion tests

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch
from budget_tracker.currency.exchange_rate_provider import ExchangeRateProvider
from budget_tracker.currency.converter import CurrencyConverter


class TestExchangeRateProvider:
    @pytest.fixture
    def provider(self):
        return ExchangeRateProvider()

    def test_fetch_rate_for_date(self, provider):
        """Test fetching exchange rate for a specific date"""
        # Mock the API response
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45}
        }

        with patch('httpx.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            rate = provider.get_rate("EUR", "DKK", date(2025, 10, 10))
            assert rate == Decimal("7.45")

    def test_dkk_to_dkk_returns_one(self, provider):
        """Test that DKK to DKK conversion returns 1.0"""
        rate = provider.get_rate("DKK", "DKK", date(2025, 10, 10))
        assert rate == Decimal("1.0")

    def test_cache_rate_to_avoid_repeated_calls(self, provider):
        """Test that rates are cached to avoid redundant API calls"""
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45}
        }

        with patch('httpx.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            # First call
            rate1 = provider.get_rate("EUR", "DKK", date(2025, 10, 10))
            # Second call with same parameters
            rate2 = provider.get_rate("EUR", "DKK", date(2025, 10, 10))

            # API should only be called once
            assert mock_get.call_count == 1
            assert rate1 == rate2

    def test_fallback_on_api_error(self, provider):
        """Test fallback behavior when API is unavailable"""
        with patch('httpx.get', side_effect=Exception("API Error")):
            with pytest.raises(ValueError, match="Unable to fetch exchange rate"):
                provider.get_rate("EUR", "DKK", date(2025, 10, 10))


class TestCurrencyConverter:
    @pytest.fixture
    def converter(self):
        return CurrencyConverter()

    def test_convert_eur_to_dkk(self, converter):
        """Test converting EUR amount to DKK"""
        mock_response = {
            "amount": 1.0,
            "base": "EUR",
            "date": "2025-10-10",
            "rates": {"DKK": 7.45}
        }

        with patch('httpx.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            result = converter.convert(
                amount=Decimal("100.00"),
                from_currency="EUR",
                to_currency="DKK",
                transaction_date=date(2025, 10, 10)
            )

            assert result == Decimal("745.00")

    def test_no_conversion_for_dkk(self, converter):
        """Test that DKK amounts are not converted"""
        result = converter.convert(
            amount=Decimal("100.00"),
            from_currency="DKK",
            to_currency="DKK",
            transaction_date=date(2025, 10, 10)
        )
        assert result == Decimal("100.00")

    def test_preserve_decimal_precision(self, converter):
        """Test that decimal precision is maintained"""
        mock_response = {
            "amount": 1.0,
            "base": "USD",
            "date": "2025-10-10",
            "rates": {"DKK": 6.87}
        }

        with patch('httpx.get') as mock_get:
            mock_get.return_value.json.return_value = mock_response
            mock_get.return_value.status_code = 200

            result = converter.convert(
                amount=Decimal("123.45"),
                from_currency="USD",
                to_currency="DKK",
                transaction_date=date(2025, 10, 10)
            )

            # 123.45 * 6.87 = 848.1015, rounded to 2 decimals = 848.10
            assert result == Decimal("848.10")
```

#### 2. Exchange Rate Provider Implementation

**File**: `src/budget_tracker/currency/exchange_rate_provider.py`
**Changes**: Implement exchange rate fetching

```python
import httpx
from datetime import date
from decimal import Decimal
from typing import Dict, Tuple
from functools import lru_cache


class ExchangeRateProvider:
    """
    Fetch historical exchange rates using Frankfurter API.

    Frankfurter is a free, open-source API for current and historical
    foreign exchange rates published by the European Central Bank.
    https://www.frankfurter.app/
    """

    BASE_URL = "https://api.frankfurter.app"

    def __init__(self):
        self._cache: Dict[Tuple[str, str, date], Decimal] = {}

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        transaction_date: date
    ) -> Decimal:
        """
        Get exchange rate for a specific date.

        Args:
            from_currency: Source currency code (e.g., "EUR", "USD")
            to_currency: Target currency code (e.g., "DKK")
            transaction_date: Date of the transaction

        Returns:
            Exchange rate as Decimal

        Raises:
            ValueError: If rate cannot be fetched
        """
        # No conversion needed for same currency
        if from_currency == to_currency:
            return Decimal("1.0")

        # Check cache first
        cache_key = (from_currency, to_currency, transaction_date)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch from API
        try:
            url = f"{self.BASE_URL}/{transaction_date.isoformat()}"
            params = {
                "from": from_currency,
                "to": to_currency
            }

            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            rate = Decimal(str(data["rates"][to_currency]))

            # Cache the result
            self._cache[cache_key] = rate

            return rate

        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ValueError(
                f"Unable to fetch exchange rate for {from_currency} to {to_currency} "
                f"on {transaction_date}: {e}"
            )

    def clear_cache(self):
        """Clear the exchange rate cache"""
        self._cache.clear()
```

#### 3. Currency Converter Implementation

**File**: `src/budget_tracker/currency/converter.py`
**Changes**: Implement currency conversion logic

```python
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from budget_tracker.currency.exchange_rate_provider import ExchangeRateProvider


class CurrencyConverter:
    """Convert transaction amounts to DKK using historical exchange rates"""

    def __init__(self):
        self.provider = ExchangeRateProvider()

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        transaction_date: date
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code (typically "DKK")
            transaction_date: Date to use for exchange rate

        Returns:
            Converted amount rounded to 2 decimal places
        """
        # No conversion needed for same currency
        if from_currency == to_currency:
            return amount

        # Get exchange rate for the transaction date
        rate = self.provider.get_rate(from_currency, to_currency, transaction_date)

        # Convert and round to 2 decimal places
        converted = amount * rate
        return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

#### 4. Update Column Mapping Interactive Flow

**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add currency selection to interactive mapping

```python
# Add after description column selection:

    # Currency handling
    console.print("\n[bold]Currency Configuration[/bold]")
    has_currency_column = Prompt.ask(
        "Does the CSV have a currency column?",
        choices=["y", "n"],
        default="n"
    )

    currency_col = None
    default_currency = "DKK"

    if has_currency_column == "y":
        currency_col = Prompt.ask(
            "Which column contains the currency code?",
            choices=available_columns
        )
    else:
        # Ask for default currency
        console.print("\nCommon currencies:")
        console.print("  1. DKK (Danish Krone)")
        console.print("  2. EUR (Euro)")
        console.print("  3. USD (US Dollar)")
        console.print("  4. GBP (British Pound)")
        console.print("  5. SEK (Swedish Krona)")
        console.print("  6. NOK (Norwegian Krone)")
        console.print("  7. Other")

        currency_choice = Prompt.ask("Select currency", default="1")

        currency_map = {
            "1": "DKK",
            "2": "EUR",
            "3": "USD",
            "4": "GBP",
            "5": "SEK",
            "6": "NOK",
            "7": Prompt.ask("Enter currency code (e.g., CHF, JPY)")
        }

        default_currency = currency_map.get(currency_choice, "DKK")

    # Update mapping creation to include currency
    mapping = BankMapping(
        bank_name=bank_name,
        column_mapping=ColumnMapping(
            date_column=date_col,
            amount_column=amount_col,
            description_column=desc_col,
            currency_column=currency_col
        ),
        date_format=date_format,
        default_currency=default_currency
    )
```

#### 5. Update Settings

**File**: `src/budget_tracker/config/settings.py`
**Changes**: Add currency conversion settings

```python
class Settings(BaseSettings):
    """Application settings"""
    # ... existing settings ...

    # Currency conversion
    enable_currency_conversion: bool = True
    target_currency: str = "DKK"
    exchange_rate_cache_size: int = 1000
```

#### 6. Update Transaction Normalizer

**File**: `src/budget_tracker/normalizer/transformer.py`
**Changes**: Integrate currency conversion

```python
from budget_tracker.currency.converter import CurrencyConverter

class TransactionNormalizer:
    """Transform raw CSV data into standardized format"""

    def __init__(self):
        self.currency_converter = CurrencyConverter()

    def normalize(
        self,
        raw: RawTransaction,
        mapping: BankMapping,
        category: str,
        subcategory: Optional[str] = None,
        confidence: float = 1.0
    ) -> Optional[StandardTransaction]:
        """Normalize a raw transaction to standard format with currency conversion."""
        try:
            # Parse date
            date_str = raw.data.get(mapping.column_mapping.date_column)
            if not date_str:
                return None
            parsed_date = self._parse_date(date_str, mapping.date_format)

            # Parse amount
            amount_str = raw.data.get(mapping.column_mapping.amount_column)
            if not amount_str:
                return None
            amount = self._parse_amount(amount_str, mapping.decimal_separator)

            # Determine currency
            if mapping.column_mapping.currency_column:
                currency = raw.data.get(mapping.column_mapping.currency_column, mapping.default_currency)
            else:
                currency = mapping.default_currency

            # Convert to DKK
            amount_dkk = self.currency_converter.convert(
                amount=amount,
                from_currency=currency.upper(),
                to_currency="DKK",
                transaction_date=parsed_date
            )

            # Get description
            description = raw.data.get(mapping.column_mapping.description_column, "")

            return StandardTransaction(
                date=parsed_date,
                category=category,
                subcategory=subcategory,
                amount=amount_dkk,
                source=mapping.bank_name,
                description=description,
                confidence=confidence
            )
        except (ValueError, InvalidOperation) as e:
            # Log error and skip malformed transaction
            return None
```

### Success Criteria:

#### Automated Verification:

- [ ] Currency converter tests pass: `pytest tests/unit/test_currency_converter.py -v`
- [ ] Can fetch exchange rates from Frankfurter API
- [ ] Rate caching works correctly
- [ ] Currency conversion maintains decimal precision
- [ ] DKK to DKK conversion returns original amount
- [ ] **Type checking passes with strict mode: `mypy src/budget_tracker/currency/ --strict`**
- [ ] **Linting passes with zero errors: `ruff check src/budget_tracker/currency/`**

#### Manual Verification:

- [ ] Test with transactions in different currencies (EUR, USD, GBP)
- [ ] Verify converted amounts are accurate
- [ ] Check that exchange rates match historical data
- [ ] Confirm caching reduces API calls for same dates
- [ ] Error messages are clear when API is unavailable

---

## Phase 4: LLM Integration for Categorization (TDD)

### Overview

Integrate Ollama for local LLM-based transaction categorization with confidence scoring and user confirmation for uncertain cases.

### Changes Required:

#### 1. LLM Categorizer Tests

**File**: `tests/unit/test_categorizer.py`
**Changes**: Write LLM integration tests

```python
import pytest
from unittest.mock import Mock, patch
from budget_tracker.categorizer.llm_categorizer import LLMCategorizer, CategoryResult
from budget_tracker.config.settings import settings


class TestLLMCategorizer:
    @pytest.fixture
    def categorizer(self):
        return LLMCategorizer()

    @pytest.fixture
    def mock_ollama_response(self):
        return {
            "response": '{"category": "Food & Dining", "subcategory": "Restaurants", "confidence": 0.95}'
        }

    def test_categorize_transaction(self, categorizer, mock_ollama_response):
        """Test categorizing a transaction description"""
        with patch('ollama.generate', return_value=mock_ollama_response):
            result = categorizer.categorize("Cafe Central - Copenhagen")
            assert result.category == "Food & Dining"
            assert result.subcategory == "Restaurants"
            assert result.confidence == 0.95

    def test_low_confidence_detection(self, categorizer):
        """Test detecting low confidence categorizations"""
        mock_response = {
            "response": '{"category": "Other", "subcategory": "Uncategorized", "confidence": 0.3}'
        }
        with patch('ollama.generate', return_value=mock_response):
            result = categorizer.categorize("XYZABC123")
            assert result.confidence < 0.5
            assert result.needs_confirmation is True

    def test_fallback_to_other_on_error(self, categorizer):
        """Test falling back to Other category on LLM error"""
        with patch('ollama.generate', side_effect=Exception("Connection error")):
            result = categorizer.categorize("Some transaction")
            assert result.category == "Other"
            assert result.subcategory == "Uncategorized"

    def test_prompt_includes_category_list(self, categorizer):
        """Test that prompt includes available categories"""
        with patch('ollama.generate') as mock_generate:
            categorizer.categorize("Test transaction")
            # Verify prompt was constructed correctly
            call_args = mock_generate.call_args
            prompt = call_args[1]['prompt']
            assert "Food & Dining" in prompt
            assert "Transportation" in prompt

    def test_batch_categorization(self, categorizer):
        """Test categorizing multiple transactions"""
        descriptions = [
            "Cafe Central",
            "Metro ticket",
            "Supermarket"
        ]
        results = categorizer.categorize_batch(descriptions)
        assert len(results) == 3
        assert all(isinstance(r, CategoryResult) for r in results)
```

**File**: `src/budget_tracker/categorizer/llm_categorizer.py`
**Changes**: Implement LLM categorization

````python
import ollama
from typing import List, Optional
from pydantic import BaseModel
import json
from budget_tracker.config.settings import settings


class CategoryResult(BaseModel):
    """Result of LLM categorization"""
    category: str
    subcategory: Optional[str] = None
    confidence: float
    needs_confirmation: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        # Mark for confirmation if confidence is low
        if self.confidence < 0.6:
            self.needs_confirmation = True


class LLMCategorizer:
    """Categorize transactions using local LLM via Ollama"""

    def __init__(self):
        self.categories = settings.load_categories()
        self.model = settings.ollama_model
        self.base_url = settings.ollama_base_url

    def categorize(self, description: str) -> CategoryResult:
        """
        Categorize a single transaction description.

        Args:
            description: Transaction description text

        Returns:
            CategoryResult with category, subcategory, and confidence
        """
        prompt = self._build_prompt(description)

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.1,  # Low temp for consistent categorization
                }
            )

            result = self._parse_response(response['response'])
            return result
        except Exception as e:
            # Fallback to Other category on error
            return CategoryResult(
                category="Other",
                subcategory="Uncategorized",
                confidence=0.0,
                needs_confirmation=True
            )

    def categorize_batch(self, descriptions: List[str]) -> List[CategoryResult]:
        """Categorize multiple transactions"""
        return [self.categorize(desc) for desc in descriptions]

    def _build_prompt(self, description: str) -> str:
        """Build categorization prompt with context"""
        categories_text = self._format_categories()

        prompt = f"""You are a financial transaction categorizer. Analyze the transaction description and categorize it.

Available categories and subcategories:
{categories_text}

Transaction description: "{description}"

Respond with ONLY a JSON object in this exact format:
{{"category": "Category Name", "subcategory": "Subcategory Name", "confidence": 0.95}}

Confidence should be 0.0 to 1.0 where:
- 0.9-1.0: Very certain (e.g., "SPOTIFY.COM" -> Entertainment/Streaming Services)
- 0.7-0.9: Confident (e.g., "Cafe Central" -> Food & Dining/Coffee & Cafes)
- 0.4-0.7: Uncertain (e.g., "ABC123" -> needs user confirmation)
- 0.0-0.4: Very uncertain (use "Other/Uncategorized")

Choose the most specific subcategory possible. If description is unclear, use "Other/Uncategorized".
"""
        return prompt

    def _format_categories(self) -> str:
        """Format categories for prompt"""
        lines = []
        for cat in self.categories['categories']:
            lines.append(f"- {cat['name']}")
            for subcat in cat['subcategories']:
                lines.append(f"  - {subcat}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> CategoryResult:
        """Parse LLM JSON response"""
        try:
            # Clean response (remove markdown code blocks if present)
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]

            data = json.loads(clean_response)
            return CategoryResult(**data)
        except (json.JSONDecodeError, KeyError):
            # Fallback if parsing fails
            return CategoryResult(
                category="Other",
                subcategory="Uncategorized",
                confidence=0.0
            )
````

#### 2. Interactive Confirmation

**File**: `src/budget_tracker/cli/confirmation.py`
**Changes**: User confirmation for uncertain categorizations

```python
from typing import List
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from budget_tracker.categorizer.llm_categorizer import CategoryResult
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.config.settings import settings

console = Console()


def confirm_uncertain_categories(
    transactions: List[StandardTransaction]
) -> List[StandardTransaction]:
    """
    Show transactions with low confidence and ask for user confirmation.

    Args:
        transactions: List of categorized transactions

    Returns:
        Updated list with user-confirmed categories
    """
    uncertain = [t for t in transactions if t.confidence < 0.6]

    if not uncertain:
        return transactions

    console.print(f"\n[yellow]⚠[/yellow] Found {len(uncertain)} transactions needing review:")

    categories = settings.load_categories()
    category_names = [c['name'] for c in categories['categories']]

    for transaction in uncertain:
        console.print(f"\n[bold]Transaction:[/bold] {transaction.description}")
        console.print(f"[dim]Amount: {transaction.amount} DKK[/dim]")
        console.print(f"[dim]Suggested: {transaction.category} (confidence: {transaction.confidence:.0%})[/dim]")

        choice = Prompt.ask(
            "Accept suggestion?",
            choices=["y", "n", "s"],
            default="y"
        )

        if choice == "y":
            continue  # Keep suggested category
        elif choice == "n":
            # Let user pick category
            console.print("\nAvailable categories:")
            for i, cat in enumerate(category_names, 1):
                console.print(f"  {i}. {cat}")

            cat_choice = Prompt.ask(
                "Select category number",
                choices=[str(i) for i in range(1, len(category_names) + 1)]
            )
            new_category = category_names[int(cat_choice) - 1]
            transaction.category = new_category
            transaction.confidence = 1.0  # User-confirmed
        else:  # skip
            transaction.category = "Other"
            transaction.subcategory = "Uncategorized"

    return transactions
```

### Success Criteria:

#### Automated Verification:

- [ ] LLM categorizer tests pass: `pytest tests/unit/test_categorizer.py -v`
- [ ] Can connect to Ollama: Test with `ollama list`
- [ ] Prompt construction includes all categories
- [ ] Confidence thresholds work correctly
- [ ] Fallback to "Other" works on errors
- [ ] **Type checking passes with strict mode: `mypy src/budget_tracker/categorizer/ --strict`**
- [ ] **Linting passes with zero errors: `ruff check src/budget_tracker/categorizer/`**

#### Manual Verification:

- [ ] Ollama is running: `ollama serve` (in background)
- [ ] Model is downloaded: `ollama pull llama3.2:3b`
- [ ] Categorization is accurate for common transactions
- [ ] Low confidence triggers user confirmation
- [ ] User can override LLM suggestions successfully

---

## Phase 5: Export & Output (TDD)

### Overview

Generate standardized CSV output, handle multiple file combination, and implement configurable output locations.

### Changes Required:

#### 1. Exporter Tests

**File**: `tests/unit/test_exporter.py`
**Changes**: Write export tests

```python
import pytest
from pathlib import Path
from datetime import date
from decimal import Decimal
import pandas as pd
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.models.transaction import StandardTransaction


class TestCSVExporter:
    @pytest.fixture
    def sample_transactions(self):
        return [
            StandardTransaction(
                date=date(2025, 10, 10),
                category="Food & Dining",
                subcategory="Restaurants",
                amount=Decimal("-125.50"),
                source="Danske Bank",
                description="Cafe Central"
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                subcategory="Public Transit",
                amount=Decimal("-24.00"),
                source="Nordea",
                description="Metro ticket"
            ),
        ]

    @pytest.fixture
    def exporter(self, tmp_path):
        return CSVExporter(output_dir=tmp_path)

    def test_export_to_csv(self, exporter, sample_transactions, tmp_path):
        """Test exporting transactions to CSV"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        assert output_file.exists()

        # Verify CSV content
        df = pd.read_csv(output_file)
        assert len(df) == 2
        assert "Date" in df.columns
        assert "Category" in df.columns
        assert "Amount (DKK)" in df.columns
        assert "Source" in df.columns

    def test_correct_column_order(self, exporter, sample_transactions, tmp_path):
        """Test that columns are in correct order"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        df = pd.read_csv(output_file)
        expected_columns = ["Date", "Category", "Amount (DKK)", "Source"]
        assert df.columns.tolist() == expected_columns

    def test_date_format_in_output(self, exporter, sample_transactions, tmp_path):
        """Test that dates are formatted correctly"""
        output_file = tmp_path / "output.csv"
        exporter.export(sample_transactions, output_file)

        df = pd.read_csv(output_file)
        assert df.iloc[0]["Date"] == "2025-10-10"

    def test_combine_multiple_sources(self, exporter, tmp_path):
        """Test combining transactions from multiple banks"""
        transactions = [
            StandardTransaction(
                date=date(2025, 10, 10),
                category="Food & Dining",
                amount=Decimal("-100"),
                source="Bank A",
            ),
            StandardTransaction(
                date=date(2025, 10, 11),
                category="Transportation",
                amount=Decimal("-50"),
                source="Bank B",
            ),
        ]

        output_file = tmp_path / "combined.csv"
        exporter.export(transactions, output_file)

        df = pd.read_csv(output_file)
        assert len(df) == 2
        assert set(df["Source"].unique()) == {"Bank A", "Bank B"}

    def test_sort_by_date(self, exporter, sample_transactions, tmp_path):
        """Test that output is sorted by date"""
        # Add transactions in reverse order
        unsorted = [sample_transactions[1], sample_transactions[0]]

        output_file = tmp_path / "sorted.csv"
        exporter.export(unsorted, output_file)

        df = pd.read_csv(output_file)
        dates = pd.to_datetime(df["Date"])
        assert dates.is_monotonic_increasing
```

**File**: `src/budget_tracker/exporters/csv_exporter.py`
**Changes**: Implement CSV export

```python
from pathlib import Path
from typing import List
import pandas as pd
from budget_tracker.models.transaction import StandardTransaction


class CSVExporter:
    """Export standardized transactions to CSV"""

    def __init__(self, output_dir: Path = None):
        from budget_tracker.config.settings import settings
        self.output_dir = output_dir or settings.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        transactions: List[StandardTransaction],
        output_file: Path
    ) -> Path:
        """
        Export transactions to standardized CSV.

        Args:
            transactions: List of standardized transactions
            output_file: Output file path

        Returns:
            Path to created file
        """
        # Convert to DataFrame
        data = []
        for t in transactions:
            row = {
                "Date": t.date.strftime("%Y-%m-%d"),
                "Category": f"{t.category}" + (f"/{t.subcategory}" if t.subcategory else ""),
                "Amount (DKK)": float(t.amount),
                "Source": t.source,
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Sort by date
        df = df.sort_values("Date")

        # Ensure column order
        df = df[["Date", "Category", "Amount (DKK)", "Source"]]

        # Write to CSV
        df.to_csv(output_file, index=False)

        return output_file
```

#### 2. Summary Statistics (Optional)

**File**: `src/budget_tracker/exporters/summary.py`
**Changes**: Generate transaction summary

```python
from typing import List
from decimal import Decimal
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from budget_tracker.models.transaction import StandardTransaction

console = Console()


def print_summary(transactions: List[StandardTransaction]):
    """Print summary statistics of processed transactions"""
    total_transactions = len(transactions)
    total_expenses = sum(t.amount for t in transactions if t.amount < 0)
    total_income = sum(t.amount for t in transactions if t.amount > 0)

    # By category
    by_category = defaultdict(Decimal)
    for t in transactions:
        if t.amount < 0:  # Only expenses
            by_category[t.category] += abs(t.amount)

    # By source
    by_source = defaultdict(int)
    for t in transactions:
        by_source[t.source] += 1

    console.print("\n[bold]Transaction Summary[/bold]")
    console.print(f"Total transactions: {total_transactions}")
    console.print(f"Total expenses: {total_expenses:.2f} DKK")
    console.print(f"Total income: {total_income:.2f} DKK")

    # Category breakdown
    if by_category:
        console.print("\n[bold]Expenses by Category:[/bold]")
        table = Table(show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Amount (DKK)", justify="right", style="magenta")

        for category, amount in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            table.add_row(category, f"{amount:.2f}")

        console.print(table)

    # Source breakdown
    console.print("\n[bold]Transactions by Source:[/bold]")
    for source, count in sorted(by_source.items()):
        console.print(f"  {source}: {count} transactions")
```

### Success Criteria:

#### Automated Verification:

- [ ] Exporter tests pass: `pytest tests/unit/test_exporter.py -v`
- [ ] CSV output has correct columns in correct order
- [ ] Dates are formatted as YYYY-MM-DD
- [ ] Transactions are sorted by date
- [ ] Multiple sources combine correctly
- [ ] **Type checking passes with strict mode: `mypy src/budget_tracker/exporters/ --strict`**
- [ ] **Linting passes with zero errors: `ruff check src/budget_tracker/exporters/`**

#### Manual Verification:

- [ ] Output CSV opens correctly in Excel/Google Sheets
- [ ] Category format is readable (Category/Subcategory)
- [ ] Summary statistics are accurate
- [ ] File is written to correct location

---

## Phase 6: CLI Integration & End-to-End Flow

### Overview

Integrate all components into a cohesive CLI application with the main processing workflow.

### Changes Required:

#### 1. Main CLI Application

**File**: `src/budget_tracker/cli/main.py`
**Changes**: Implement main CLI interface

```python
import typer
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from budget_tracker.config.settings import settings
from budget_tracker.parsers.csv_parser import CSVParser
from budget_tracker.parsers.multi_file import MultiFileProcessor
from budget_tracker.cli.mapping import interactive_column_mapping, save_mapping, load_mapping
from budget_tracker.normalizer.batch_processor import BatchNormalizer
from budget_tracker.categorizer.llm_categorizer import LLMCategorizer
from budget_tracker.cli.confirmation import confirm_uncertain_categories
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.exporters.summary import print_summary

app = typer.Typer(help="Bank Statement Normalizer - Standardize and categorize your transactions")
console = Console()


@app.command()
def process(
    files: List[Path] = typer.Argument(..., help="CSV files to process"),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV file path"
    ),
):
    """
    Process bank statement CSV files and generate standardized output.

    Examples:
        budget-tracker process bank1.csv
        budget-tracker process bank1.csv bank2.csv --output results.csv
    """
    console.print("[bold]Budget Tracker - Bank Statement Normalizer[/bold]\n")

    # Ensure directories exist
    settings.ensure_directories()

    # Validate input files
    for file in files:
        if not file.exists():
            console.print(f"[red]✗[/red] File not found: {file}")
            raise typer.Exit(1)

    console.print(f"Processing {len(files)} file(s)...")

    # Step 1: Parse and map columns
    parser = CSVParser()
    all_raw_transactions = []

    for file in files:
        console.print(f"\n[cyan]Processing:[/cyan] {file.name}")

        # Try to load saved mapping
        mapping = load_mapping(file.stem, settings.mappings_file)

        if not mapping:
            # Interactive column mapping
            df, columns = parser.parse_file(file)
            console.print(f"Detected {len(columns)} columns: {', '.join(columns)}")

            mapping = interactive_column_mapping(file, columns)
            if not mapping:
                console.print("[red]Mapping cancelled[/red]")
                raise typer.Exit(1)

            save_mapping(mapping, settings.mappings_file)
        else:
            console.print(f"[green]✓[/green] Using saved mapping for {mapping.bank_name}")

        # Parse with mapping
        raw_transactions = parser.load_with_mapping(file, mapping)
        console.print(f"[green]✓[/green] Loaded {len(raw_transactions)} transactions")
        all_raw_transactions.extend(raw_transactions)

    # Step 2: Categorize with LLM
    console.print("\n[cyan]Categorizing transactions with local LLM...[/cyan]")
    categorizer = LLMCategorizer()

    categorized_transactions = []
    for raw in all_raw_transactions:
        # Get description for categorization
        desc = raw.data.get("description", "")
        result = categorizer.categorize(desc)

        # Create standardized transaction (will be normalized in next step)
        # For now, store category info
        raw.category_result = result

    console.print(f"[green]✓[/green] Categorized {len(all_raw_transactions)} transactions")

    # Step 3: Normalize
    console.print("\n[cyan]Normalizing data...[/cyan]")
    normalizer = BatchNormalizer()

    standardized = []
    for raw in all_raw_transactions:
        # Find the mapping used for this transaction
        mapping = load_mapping(Path(raw.source_file).stem, settings.mappings_file)
        if mapping:
            std = normalizer.normalizer.normalize(
                raw,
                mapping,
                category=raw.category_result.category,
                subcategory=raw.category_result.subcategory,
                confidence=raw.category_result.confidence
            )
            if std:
                standardized.append(std)

    console.print(f"[green]✓[/green] Normalized {len(standardized)} transactions")

    # Step 4: Confirm uncertain categories
    standardized = confirm_uncertain_categories(standardized)

    # Step 5: Export
    output_file = output or (settings.output_dir / settings.default_output_filename)
    exporter = CSVExporter()
    result_file = exporter.export(standardized, output_file)

    console.print(f"\n[bold green]✓ Success![/bold green]")
    console.print(f"Output written to: {result_file}")

    # Print summary
    print_summary(standardized)


@app.command()
def list_mappings():
    """List all saved bank mappings"""
    import json

    if not settings.mappings_file.exists():
        console.print("No saved mappings found.")
        return

    with open(settings.mappings_file, 'r') as f:
        mappings = json.load(f)

    console.print("\n[bold]Saved Bank Mappings:[/bold]")
    for bank_name in mappings.keys():
        console.print(f"  • {bank_name}")


if __name__ == "__main__":
    app()
```

#### 2. Update Main Entry Point

**File**: `main.py`
**Changes**: Forward to CLI app

```python
from budget_tracker.cli.main import app

if __name__ == "__main__":
    app()
```

#### 3. Integration Tests

**File**: `tests/integration/test_end_to_end.py`
**Changes**: Full end-to-end test

```python
import pytest
from pathlib import Path
from typer.testing import CliRunner
from budget_tracker.cli.main import app
import pandas as pd

runner = CliRunner()


class TestEndToEnd:
    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create sample CSV file"""
        csv_content = """Date,Amount,Description
2025-10-10,-125.50,Cafe Central Copenhagen
2025-10-11,-24.00,Metro Ticket
2025-10-12,5000.00,Salary Payment"""
        csv_file = tmp_path / "test_bank.csv"
        csv_file.write_text(csv_content)
        return csv_file

    def test_full_processing_flow(self, sample_csv, tmp_path, monkeypatch):
        """Test complete flow from CSV to output"""
        # Mock user inputs for interactive prompts
        # This would need to be implemented with proper mocking

        output_file = tmp_path / "output.csv"

        # Note: This test requires Ollama to be running
        # In CI/CD, you might want to mock the LLM calls

        # Run CLI command
        result = runner.invoke(app, [
            "process",
            str(sample_csv),
            "--output",
            str(output_file)
        ])

        # Verify output file exists
        assert output_file.exists()

        # Verify output content
        df = pd.read_csv(output_file)
        assert len(df) >= 1  # At least one transaction processed
        assert "Date" in df.columns
        assert "Category" in df.columns
```

### Success Criteria:

#### Automated Verification:

- [ ] CLI installs correctly: `pip install -e .`
- [ ] Help text displays: `budget-tracker --help`
- [ ] Integration tests pass: `pytest tests/integration/ -v`
- [ ] Can run with test CSV: `budget-tracker process tests/fixtures/sample_bank1.csv`
- [ ] **All type checking passes: `mypy src/ --strict`**
- [ ] **All linting passes: `ruff check src/`**
- [ ] **All code is properly formatted: `ruff format src/`**

#### Manual Verification:

- [ ] Full workflow completes successfully with real bank statements
- [ ] Interactive prompts are clear and user-friendly
- [ ] Error messages are helpful
- [ ] Output CSV is correctly formatted
- [ ] Summary statistics are accurate
- [ ] Can process multiple files and combine them

---

## Testing Strategy

### Code Quality Requirements

**CRITICAL: All code must meet these standards before merging:**

- ✅ **100% type annotation coverage** - Every function, method, and variable must have type hints
- ✅ **Zero ruff violations** - All linting rules must pass
- ✅ **Zero mypy errors** - Strict type checking must pass with no errors
- ✅ **Proper formatting** - Code must be formatted with `ruff format`
- ✅ **All tests passing** - Unit and integration tests must pass

**Run quality checks before every commit:**

```bash
./scripts/check_quality.sh
```

### Unit Tests

**Coverage areas:**

- Data models (transaction, bank mapping)
- CSV parsing and delimiter detection
- Date/amount normalization
- Currency conversion
- LLM categorization logic
- CSV export formatting

**Key edge cases:**

- Malformed CSV files
- Invalid date formats
- Various decimal separators (comma, dot)
- Missing columns
- Empty descriptions
- LLM connection failures
- Currency conversion errors
- Exchange rate API failures

### Integration Tests

**Scenarios:**

- End-to-end: CSV input → categorized output
- Multi-file processing
- Saved mapping reuse
- User confirmation flow
- Error recovery

### Manual Testing Steps

1. **First-time setup:**

   - Install dependencies
   - Start Ollama: `ollama serve`
   - Pull model: `ollama pull llama3.2:3b`
   - Verify categories.yaml exists

2. **Process single file:**

   - Run with sample CSV
   - Complete interactive mapping
   - Verify mapping saves correctly
   - Check output CSV format

3. **Process multiple files:**

   - Run with 2-3 different bank statements
   - Verify mappings are reused for known banks
   - Check combined output

4. **Test edge cases:**

   - Malformed CSV (missing columns)
   - Unusual date formats
   - Transactions with no description
   - Very large CSV (1000+ rows)

5. **LLM categorization quality:**
   - Sample common transactions (cafe, supermarket, transport)
   - Check confidence scores
   - Verify uncertain cases trigger confirmation
   - Test fallback to "Other" category

## Performance Considerations

**LLM Inference:**

- Using Llama 3.2 1B/3B for fast local inference
- Expected speed: ~5-10 transactions/second on modern CPU
- For large files (1000+ transactions), consider batch processing with progress bar
- Could cache common merchant categorizations for speed

**CSV Processing:**

- Pandas handles files up to millions of rows efficiently
- No performance concerns for typical bank statements (100-1000 rows)

**Memory Usage:**

- Expected: <500MB for typical use cases
- LLM model: 1B model ~700MB, 3B model ~2GB

## Migration Notes

**Initial Setup:**

1. User installs with: `pip install budget-tracker`
2. First run creates config directories automatically
3. Ollama must be installed separately: https://ollama.ai
4. Model pull required: `ollama pull llama3.2:3b`

**Configuration:**

- `config/categories.yaml` - Tracked in git, user can modify
- `config/bank_mappings.json` - Created on first use, user-specific
- `data/output/` - Default output location, ignored by git

**Currency Conversion:**

- Uses Frankfurter API (free, open-source, ECB data)
- Historical exchange rates for transaction dates
- Automatic conversion to DKK
- Supports per-transaction currency or default per bank
- Rate caching to minimize API calls

**Future Enhancements:**

- Support for more output formats (Excel, JSON)
- Transaction deduplication
- Web UI for reviewing/editing categories
- Automatic bank detection from CSV headers
- Offline exchange rate database for privacy-first option

## References

- App idea document: `.claude/thoughts/thoughts/app_idea.md`
- Ollama Python client: https://github.com/ollama/ollama-python
- Typer CLI framework: https://typer.tiangolo.com
- Pydantic V2 docs: https://docs.pydantic.dev/latest/
