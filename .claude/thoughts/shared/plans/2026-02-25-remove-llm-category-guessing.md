# Remove LLM Category Guessing — Implementation Plan

## Overview
Replace the Ollama LLM-based transaction categorization with direct user selection. Every non-transfer transaction will be categorized by the user via the existing arrow-key selection UI, with a description cache ensuring duplicate descriptions are only prompted once per run.

## Context
- **Task**: Remove LLM guessing entirely; categories picked by user
- **Research**: `.claude/thoughts/shared/research/2026-02-25-remove-llm-category-guessing.md`
- **Key decisions from research Q&A**: No persistence across runs (follow-up), one-by-one UI, remove `confidence` field, remove LLM entirely (not optional)

## Phase 1: Replace Categorization Pipeline

### Overview
Replace the LLM categorization loop in `main.py` with a new `categorize_transactions()` function that prompts the user to select categories via the existing `select_option()` UI. Remove the Ollama running check gate.

### Tasks:

#### 1. Create `categorize_transactions()` in `confirmation.py`
**File**: `src/budget_tracker/cli/confirmation.py`
**Changes**: Add a new function that takes `ParsedTransaction` list + `Settings` + `CurrencyConverter`, prompts the user to pick category/subcategory for each unique description, caches choices by description, and returns `StandardTransaction` list.

```python
def categorize_transactions(
    settings: Settings,
    transactions: list[ParsedTransaction],
    currency_converter: CurrencyConverter,
) -> list[StandardTransaction]:
    """
    Prompt user to categorize each transaction via interactive selection.
    Caches choices by description so duplicates are auto-resolved.
    """
    categories = settings.load_categories()
    category_names = [c["name"] for c in categories["categories"]]
    subcategories = [c.get("subcategories", []) for c in categories["categories"]]

    # Cache: {description: (category, subcategory)}
    confirmed_cache: dict[str, tuple[str, str | None]] = {}
    standardized: list[StandardTransaction] = []

    for parsed in transactions:
        # Convert currency
        amount_dkk = currency_converter.convert(
            amount=parsed.amount,
            from_currency=parsed.currency,
            to_currency="DKK",
            transaction_date=parsed.date,
        )

        # Check cache
        if parsed.description in confirmed_cache:
            cat, subcat = confirmed_cache[parsed.description]
            console.print(f"\n[dim]Reusing category for: {parsed.description} → {cat}[/dim]")
            standardized.append(StandardTransaction(
                date=parsed.date,
                category=cat,
                subcategory=subcat,
                amount=amount_dkk,
                source=parsed.source,
                description=parsed.description,
            ))
            continue

        # Show transaction info
        console.print(f"\n[bold]Transaction:[/bold] {parsed.description}")
        console.print(f"[dim]Amount: {amount_dkk} DKK | Date: {parsed.date}[/dim]")

        # User selects category
        new_category = select_option("\nSelect category", category_names)
        if new_category is None:
            console.print("  [red]Application error.[/red]")
            raise KeyboardInterrupt

        # Subcategory selection
        cat_index = category_names.index(new_category)
        subcat_list = subcategories[cat_index]
        new_subcategory = None
        if subcat_list:
            subcat_choices = [*subcat_list, "(Skip)"]
            subcat_selection = select_option(
                f"Select subcategory for {new_category}",
                subcat_choices,
                default="(Skip)",
            )
            new_subcategory = None if subcat_selection == "(Skip)" else subcat_selection
        else:
            console.print(f"  (No subcategories available for {new_category})")

        # Cache and create transaction
        confirmed_cache[parsed.description] = (new_category, new_subcategory)
        standardized.append(StandardTransaction(
            date=parsed.date,
            category=new_category,
            subcategory=new_subcategory,
            amount=amount_dkk,
            source=parsed.source,
            description=parsed.description,
        ))

    return standardized
```

#### 2. Remove `confirm_uncertain_categories()` from `confirmation.py`
**File**: `src/budget_tracker/cli/confirmation.py`
**Changes**: Delete the entire `confirm_uncertain_categories()` function (lines 11-101). It is fully replaced by `categorize_transactions()`.

#### 3. Update `main.py` pipeline
**File**: `src/budget_tracker/cli/main.py`
**Changes**:
- Remove the `is_ollama_running()` check (lines 71-75)
- Remove `LLMCategorizer` import and instantiation (lines 7, 143)
- Remove the LLM categorization loop (lines 170-193)
- Remove the `confirm_uncertain_categories()` call (line 200)
- Replace with a single call to `categorize_transactions()`
- Update the `CurrencyConverter` to be created before categorization (already at line 144)
- Remove import of `is_ollama_running` (line 19)
- Update import from `confirmation.py` to import `categorize_transactions` instead of `confirm_uncertain_categories`

The relevant section of `process()` (after transfer detection, around line 141) becomes:

```python
# Step 2: Categorize transactions with user selection
console.print("\n[cyan]Categorizing transactions...[/cyan]")
currency_converter = CurrencyConverter()

standardized: list[StandardTransaction] = []

# First, add confirmed transfers
for pair in confirmed_transfers:
    for parsed in [pair.outgoing, pair.incoming]:
        amount_dkk = currency_converter.convert(
            amount=parsed.amount,
            from_currency=parsed.currency,
            to_currency="DKK",
            transaction_date=parsed.date,
        )
        standardized.append(
            StandardTransaction(
                date=parsed.date,
                category="Internal Transfer",
                subcategory="Transfer",
                amount=amount_dkk,
                source=parsed.source,
                description=parsed.description,
            )
        )

# Categorize remaining transactions via user selection
if transactions_to_categorize:
    user_categorized = categorize_transactions(
        _settings, transactions_to_categorize, currency_converter
    )
    standardized.extend(user_categorized)

console.print(
    f"[green]✓[/green] Categorized and normalized {len(standardized)} transactions"
)

# Step 5: Export (no more Step 4 confirmation — it's now part of Step 2)
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`

#### Manual Verification:
- [ ] Run `budget-tracker process` with a CSV — each transaction prompts for category selection
- [ ] Duplicate descriptions are auto-resolved from cache (prompted only once)
- [ ] Ctrl+C gracefully exits during selection
- [x] App starts without Ollama running

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Remove `confidence` Field and LLM Code

### Overview
Remove the `confidence` field from `StandardTransaction`, delete the LLM categorizer module, Ollama utility, and Ollama-related settings. Clean up all references.

### Tasks:

#### 1. Remove `confidence` from `StandardTransaction`
**File**: `src/budget_tracker/models/transaction.py`
**Changes**:
- Delete line 24: `confidence: float = Field(default=1.0, ge=0.0, le=1.0)`
- Update model config comment from "Allow modifications for LLM categorization" to "Allow modifications for categorization"

#### 2. Remove `confidence` from transfer construction in `main.py`
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Remove `confidence=1.0` from the `StandardTransaction()` constructor call for confirmed transfers (was at line 165).

#### 3. Delete LLM categorizer module
**Files to delete**:
- `src/budget_tracker/categorizer/llm_categorizer.py` — entire file
- `src/budget_tracker/categorizer/__init__.py` — entire file (empty)
- `src/budget_tracker/utils/ollama.py` — entire file

#### 4. Remove Ollama settings
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Delete lines 23-25:
```python
ollama_base_url: str = "http://localhost:11434"
ollama_model: str = "mistral"
ollama_confidence_threshold: float = 0.9
```

#### 5. Remove `ollama` from dependencies
**File**: `pyproject.toml` (or `requirements.txt` — check which dependency file is used)
**Changes**: Remove the `ollama` Python package from dependencies.

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`

#### Manual Verification:
- [x] `grep -r "confidence" src/` returns no results (except if used in comments/unrelated code)
- [x] `grep -r "ollama" src/` returns no results
- [x] `grep -r "LLMCategorizer" src/` returns no results

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 3: Update Tests

### Overview
Delete the LLM categorizer unit tests and update integration tests to remove all LLM/Ollama mocking. Integration tests should mock the new `categorize_transactions` function instead.

### Tasks:

#### 1. Delete LLM categorizer tests
**File to delete**: `tests/unit/test_categorizer.py`

#### 2. Update `test_cli.py` integration tests
**File**: `tests/integration/test_cli.py`
**Changes**:
- Remove `CategoryResult` import (line 16)
- Remove `is_ollama_running` mock from `test_full_processing_flow` and `test_process_with_transfers`
- Remove `LLMCategorizer` mock — replace with `categorize_transactions` mock
- The mock should return a list of `StandardTransaction` objects directly

For `test_full_processing_flow`:
```python
@patch("budget_tracker.cli.main.confirm_transfers")
@patch("budget_tracker.cli.main.categorize_transactions")
def test_full_processing_flow(
    self,
    mock_categorize: MagicMock,
    mock_confirm_transfers: MagicMock,
    cli_runner: CliRunner,
    settings: Settings,
    sample_csv: Path,
    make_bank_mappings: None,
):
    mock_confirm_transfers.return_value = ([], [])
    # Mock categorize_transactions to return pre-categorized transactions
    mock_categorize.return_value = [
        StandardTransaction(
            date=date(2024, 1, 15),
            category="Food & Drinks",
            subcategory="Restaurants",
            amount=Decimal("-100.00"),
            source="bank1",
            description="Cafe Central Copenhagen",
        ),
        # ... other transactions
    ]
    # ... rest of test
```

#### 3. Update `test_cli_sheets.py` integration tests
**File**: `tests/integration/test_cli_sheets.py`
**Changes**:
- Remove `CategoryResult` import
- Remove `is_ollama_running` mock
- Remove `LLMCategorizer` mock — replace with `categorize_transactions` mock
- Same pattern as `test_cli.py` updates

#### 4. Remove `confidence` from test transaction construction
**File**: `tests/unit/test_models.py`
**Changes**: No changes needed — existing tests don't use `confidence` field.

### Success Criteria:

#### Automated Verification:
- [x] All tests pass: `pytest`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`

#### Manual Verification:
- [x] `grep -r "ollama" tests/` returns no results
- [x] `grep -r "LLMCategorizer" tests/` returns no results
- [x] `grep -r "CategoryResult" tests/` returns no results

---

## References
- Research: `.claude/thoughts/shared/research/2026-02-25-remove-llm-category-guessing.md`
- `src/budget_tracker/cli/main.py:71-75` — Ollama check to remove
- `src/budget_tracker/cli/main.py:141-200` — LLM loop + confirmation to replace
- `src/budget_tracker/cli/confirmation.py:69-94` — Category selection UI to reuse
- `src/budget_tracker/cli/selection.py:36-67` — `select_option()` function
- `src/budget_tracker/categorizer/llm_categorizer.py` — Module to delete
- `src/budget_tracker/utils/ollama.py` — Utility to delete
- `src/budget_tracker/config/settings.py:23-25` — Ollama settings to remove
- `src/budget_tracker/models/transaction.py:24` — `confidence` field to remove
