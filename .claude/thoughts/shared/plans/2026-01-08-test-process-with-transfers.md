# Plan: Implement `test_process_with_transfers` Integration Test

## Overview

Write an integration test that verifies transfer detection is called during CLI processing when multiple bank statements are processed together.

## Context

The test skeleton uses fixtures that **don't exist yet** in the codebase (`cli_runner`, `temp_settings`, `sample_csv_file`, `mock_categorizer`). These need to be created as class methods or the test needs to use inline setup similar to existing tests in `test_cli_sheets.py`.

## Key Integration Points

Based on `src/budget_tracker/cli/main.py` (lines 120-126):
```python
detector = TransferDetector()
transfer_pairs, non_transfer_transactions = detector.detect(all_parsed_transactions)
confirmed_transfers, rejected_transfers = confirm_transfers(transfer_pairs)
```

## Implementation Plan

### Step 1: Add Required Imports

Add to test file:
```python
from unittest.mock import patch, MagicMock
from decimal import Decimal
from budget_tracker.parsers.csv_parser import ParsedTransaction
```

### Step 2: Create Test Class with Fixtures

Create a new test class `TestTransferIntegration` in `tests/integration/test_end_to_end.py` with these fixtures as class methods:

#### 2.1 `settings` fixture (temp_settings)
```python
@pytest.fixture
def settings(self, tmp_path: Path) -> Settings:
    """Create isolated test settings."""
    settings = Settings()
    settings.config_dir = tmp_path / "config"
    settings.data_dir = tmp_path / "data"
    settings.output_dir = tmp_path / "output"
    settings.banks_dir = tmp_path / "banks"
    settings.output_dir.mkdir(parents=True)
    settings.banks_dir.mkdir(parents=True)
    return settings
```

#### 2.2 `cli_runner` fixture
```python
@pytest.fixture
def cli_runner(self) -> CliRunner:
    return CliRunner()
```

#### 2.3 `sample_csv_file` fixture (first bank)
```python
@pytest.fixture
def sample_csv_file(self, tmp_path: Path) -> Path:
    """Create CSV with outgoing transfer."""
    csv_content = """Date,Amount,Description
2024-01-15,-100.00,Transfer to savings
2024-01-16,-50.00,Coffee shop"""
    csv_file = tmp_path / "bank1.csv"
    csv_file.write_text(csv_content)
    return csv_file
```

### Step 3: Create Bank Mapping YAML Files

Both banks need YAML config files in `settings.banks_dir`:

#### 3.1 `bank1.yaml` mapping
```yaml
bank_name: bank1
column_mapping:
  date_column: Date
  amount_column: Amount
  description_columns: [Description]
  currency_column: null
date_format: "%Y-%m-%d"
decimal_separator: "."
default_currency: DKK
```

#### 3.2 `bank2.yaml` mapping
```yaml
bank_name: bank2
column_mapping:
  date_column: Date
  amount_column: Amount
  description_columns: [Description]
  currency_column: null
date_format: "%Y-%m-%d"
decimal_separator: "."
default_currency: DKK
```

### Step 4: Implement the Test Method

```python
@patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
@patch("budget_tracker.cli.transfer_confirmation.confirm_transfers")
@patch("budget_tracker.cli.main.LLMCategorizer")
def test_process_with_transfers(
    self,
    mock_categorizer_class: MagicMock,
    mock_confirm_transfers: MagicMock,
    mock_ollama: MagicMock,
    cli_runner: CliRunner,
    settings: Settings,
    sample_csv_file: Path,
) -> None:
    """Test that transfer detection is called during processing."""

    # 1. Setup mock_confirm_transfers to return empty (no confirmed transfers)
    mock_confirm_transfers.return_value = ([], [])

    # 2. Setup mock categorizer
    mock_cat_instance = MagicMock()
    mock_cat_instance.categorize.return_value = CategoryResult(
        category="Food & Drinks",
        subcategory="Restaurants",
        confidence=0.9,
    )
    mock_categorizer_class.return_value = mock_cat_instance

    # 3. Create second CSV file (incoming transfer from different bank)
    second_csv = settings.output_dir / "bank2.csv"
    second_csv.write_text(
        "Date,Amount,Description\n2024-01-15,100.00,Transfer from checking\n"
    )

    # 4. Create bank mapping YAML files
    bank1_mapping = {
        "bank_name": "bank1",
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
    bank2_mapping = {
        "bank_name": "bank2",
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

    (settings.banks_dir / "bank1.yaml").write_text(yaml.safe_dump(bank1_mapping))
    (settings.banks_dir / "bank2.yaml").write_text(yaml.safe_dump(bank2_mapping))

    # 5. Create app with test settings and invoke CLI
    test_app = create_app(settings=settings)
    result = cli_runner.invoke(
        test_app,
        ["process", str(sample_csv_file), str(second_csv), "-b", "bank1", "-b", "bank2"],
    )

    # 6. Assertions
    # Verify confirm_transfers was called (transfer detection ran)
    mock_confirm_transfers.assert_called_once()

    # Verify the call received TransferPair objects
    call_args = mock_confirm_transfers.call_args[0][0]  # First positional arg
    assert isinstance(call_args, list)
    # Should detect the 100.00 transfer pair (same amount, same date, different banks)
    assert len(call_args) >= 1  # At least one transfer detected
```

### Step 5: Key Assertions to Verify

1. **`mock_confirm_transfers.assert_called_once()`** - Confirms transfer detection pipeline ran
2. **Check call arguments** - Verify TransferPair objects were passed
3. **Verify transfer detection logic** - The -100.00 (bank1) and +100.00 (bank2) on same date should be detected as a transfer pair
4. **Exit code** - `assert result.exit_code == 0` for successful processing

## Files to Modify

| File | Action |
|------|--------|
| `tests/integration/test_end_to_end.py` | Add new `TestTransferIntegration` class with fixtures and test method |

## Verification

Run the test with:
```bash
pytest tests/integration/test_end_to_end.py::TestTransferIntegration::test_process_with_transfers -v
```

## Notes

- The test focuses on verifying the **integration point exists** - that `confirm_transfers` is called during processing
- Full transfer detection logic is already tested in `tests/unit/test_transfer_detector.py`
- Full confirmation UI is already tested in `tests/unit/test_transfer_confirmation.py`
- This test bridges the gap by ensuring the CLI wires these components together correctly
