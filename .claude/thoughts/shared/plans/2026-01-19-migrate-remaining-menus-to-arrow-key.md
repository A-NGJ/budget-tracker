# Migrate Remaining Menus to Arrow-Key Navigation

## Overview
Migrate menu selections in `mapping.py` and `confirmation.py` to use `select_option()` for arrow-key navigation, while keeping y/n/s confirmation prompts and text input prompts unchanged.

## Current State Analysis
- `selection.py` provides `select_option()` with questionary/Rich fallback
- `blacklist.py` already migrated to arrow-key selection
- `mapping.py` has 6 menu selections using numbered `Prompt.ask()`
- `confirmation.py` has 2 menu selections using numbered `Prompt.ask()`

### Key Discoveries:
- Menu selections display numbered lists then call `Prompt.ask()` with number choices
- Some menus have an "Other" option that triggers text input (currency:95, date format:121)
- `confirmation.py:84` subcategory selection allows empty string to skip

## Desired End State
- All menu selections use `select_option()` for arrow-key navigation
- y/n and y/n/s prompts remain unchanged (faster for experienced users)
- Text input prompts remain unchanged
- Consistent UX across all CLI interactions

## What We're NOT Doing
- Migrating y/n confirmations (`mapping.py:59,76,176`)
- Migrating y/n/s prompts (`confirmation.py:59`)
- Migrating y/n/a/s prompts (`transfer_confirmation.py:61`)
- Migrating text input prompts (bank name, custom values)

## Implementation Approach
Update each file to import `select_option` and replace numbered menu patterns with direct choice lists.

---

## Phase 1: Migrate mapping.py Menu Selections

### Overview
Replace 6 numbered menu selections in the column mapping flow with `select_option()`.

### Changes Required:

#### 1. Update Imports
**File**: `src/budget_tracker/cli/mapping.py`
**Changes**: Add select_option import

```python
from budget_tracker.cli.selection import select_option
```

#### 2. Replace Column Selection Prompts
**File**: `src/budget_tracker/cli/mapping.py`

**Date column (line 33)**:
```python
# Before:
date_col = Prompt.ask("Which column contains the transaction date?", choices=columns)

# After:
date_col = select_option("Which column contains the transaction date?", columns)
```

**Amount column (line 36)**:
```python
# Before:
amount_col = Prompt.ask("Which column contains the amount?", choices=columns)

# After:
amount_col = select_option("Which column contains the amount?", columns)
```

**Description column (line 63-66)**:
```python
# Before:
desc_col = Prompt.ask(
    "Which column contains description/text?" if not desc_cols else "Select another column",
    choices=remaining_cols,
)

# After:
desc_col = select_option(
    "Which column contains description/text?" if not desc_cols else "Select another column",
    remaining_cols,
)
```

**Currency column (line 83)**:
```python
# Before:
currency_col = Prompt.ask("Which column contains the currency code?", choices=columns)

# After:
currency_col = select_option("Which column contains the currency code?", columns)
```

#### 3. Replace Currency Choice Menu
**File**: `src/budget_tracker/cli/mapping.py`
**Lines**: 86-109

```python
# Before:
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
}

if currency_choice == "7":
    default_currency = Prompt.ask("Enter currency code (e.g., CHF, JPY)")
else:
    default_currency = currency_map.get(currency_choice, "DKK")

# After:
currency_choices = [
    "DKK (Danish Krone)",
    "EUR (Euro)",
    "USD (US Dollar)",
    "GBP (British Pound)",
    "SEK (Swedish Krona)",
    "NOK (Norwegian Krone)",
    "Other",
]
currency_selection = select_option("Select currency", currency_choices, default="DKK (Danish Krone)")

if currency_selection == "Other":
    default_currency = Prompt.ask("Enter currency code (e.g., CHF, JPY)")
else:
    # Extract currency code from selection (e.g., "DKK (Danish Krone)" -> "DKK")
    default_currency = currency_selection.split()[0]
```

#### 4. Replace Date Format Menu
**File**: `src/budget_tracker/cli/mapping.py`
**Lines**: 112-139

```python
# Before:
console.print("\n[bold]Date Format Configuration[/bold]")
console.print("What date format does your CSV use?")
console.print("  1. DD-MM-YYYY (e.g., 31-12-2024)")
console.print("  2. YYYY-MM-DD (e.g., 2024-12-31)")
console.print("  3. MM/DD/YYYY (e.g., 12/31/2024)")
console.print("  4. DD/MM/YYYY (e.g., 31/12/2024)")
console.print("  5. YYYY/MM/DD (e.g., 2024/12/31)")
console.print("  6. Other")

date_format_choice = Prompt.ask(
    "Select date format", choices=["1", "2", "3", "4", "5", "6"], default="1"
)

date_format_map = {
    "1": "%d-%m-%Y",
    "2": "%Y-%m-%d",
    "3": "%m/%d/%Y",
    "4": "%d/%m/%Y",
    "5": "%Y/%m/%d",
}

if date_format_choice == "6":
    console.print("\nEnter custom date format using Python strftime codes:")
    console.print("  %d = day, %m = month, %Y = year")
    console.print("  Example: '%d.%m.%Y' for 31.12.2024")
    date_format = Prompt.ask("Enter date format")
else:
    date_format = date_format_map.get(date_format_choice, get_settings().default_date_format)

# After:
console.print("\n[bold]Date Format Configuration[/bold]")
date_format_choices = [
    "DD-MM-YYYY (e.g., 31-12-2024)",
    "YYYY-MM-DD (e.g., 2024-12-31)",
    "MM/DD/YYYY (e.g., 12/31/2024)",
    "DD/MM/YYYY (e.g., 31/12/2024)",
    "YYYY/MM/DD (e.g., 2024/12/31)",
    "Other",
]
date_format_map = {
    "DD-MM-YYYY (e.g., 31-12-2024)": "%d-%m-%Y",
    "YYYY-MM-DD (e.g., 2024-12-31)": "%Y-%m-%d",
    "MM/DD/YYYY (e.g., 12/31/2024)": "%m/%d/%Y",
    "DD/MM/YYYY (e.g., 31/12/2024)": "%d/%m/%Y",
    "YYYY/MM/DD (e.g., 2024/12/31)": "%Y/%m/%d",
}

date_format_selection = select_option(
    "What date format does your CSV use?",
    date_format_choices,
    default="DD-MM-YYYY (e.g., 31-12-2024)",
)

if date_format_selection == "Other":
    console.print("\nEnter custom date format using Python strftime codes:")
    console.print("  %d = day, %m = month, %Y = year")
    console.print("  Example: '%d.%m.%Y' for 31.12.2024")
    date_format = Prompt.ask("Enter date format")
else:
    date_format = date_format_map[date_format_selection]
```

#### 5. Replace Decimal Separator Menu
**File**: `src/budget_tracker/cli/mapping.py`
**Lines**: 142-148

```python
# Before:
console.print("\n[bold]Decimal Separator Configuration[/bold]")
console.print("What character is used for decimal separation?")
console.print("  1. . (dot/period) - e.g., 1234.56")
console.print("  2. , (comma) - e.g., 1234,56")

decimal_choice = Prompt.ask("Select decimal separator", choices=["1", "2"], default="1")
decimal_separator = "." if decimal_choice == "1" else ","

# After:
console.print("\n[bold]Decimal Separator Configuration[/bold]")
decimal_choices = [
    ". (dot/period) - e.g., 1234.56",
    ", (comma) - e.g., 1234,56",
]
decimal_selection = select_option(
    "What character is used for decimal separation?",
    decimal_choices,
    default=". (dot/period) - e.g., 1234.56",
)
decimal_separator = "." if decimal_selection.startswith(".") else ","
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`
- [x] Tests pass: `pytest tests/`

#### Manual Verification:
- [x] Run `budget-tracker process <csv>` with new bank
- [x] Verify arrow-key navigation works for column selection
- [x] Verify currency menu shows descriptive options
- [x] Verify date format menu shows descriptive options
- [x] Verify decimal separator menu works
- [x] Verify "Other" options still trigger text input

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Migrate confirmation.py Menu Selections

### Overview
Replace category and subcategory selection menus with `select_option()`.

### Changes Required:

#### 1. Update Imports
**File**: `src/budget_tracker/cli/confirmation.py`
**Changes**: Add select_option import

```python
from budget_tracker.cli.selection import select_option
```

#### 2. Replace Category Selection
**File**: `src/budget_tracker/cli/confirmation.py`
**Lines**: 70-77

```python
# Before:
console.print("\nAvailable categories:")
for i, cat in enumerate(category_names, 1):
    console.print(f"  {i}. {cat}")

cat_choice = Prompt.ask(
    "Select category number",
    choices=[str(i) for i in range(1, len(category_names) + 1)],
)

# After:
new_category = select_option("\nSelect category", category_names)
```

Note: This simplifies the code since `select_option` returns the actual choice, not a number.

#### 3. Replace Subcategory Selection
**File**: `src/budget_tracker/cli/confirmation.py`
**Lines**: 79-92

```python
# Before:
console.print(f"\nAvailable subcategories for {category_names[int(cat_choice) - 1]}:")
subcat_list = subcategories[int(cat_choice) - 1]
if subcat_list:
    for i, subcat in enumerate(subcat_list, 1):
        console.print(f"  {i}. {subcat}")
    subcat_choice = Prompt.ask(
        "Select subcategory number (or press Enter to skip)",
        choices=[str(i) for i in range(1, len(subcat_list) + 1)] + [""],
        default="",
    )
    new_subcategory = subcat_list[int(subcat_choice) - 1] if subcat_choice else None
else:
    console.print("  (No subcategories available)")
    new_subcategory = None
new_category = category_names[int(cat_choice) - 1]

# After:
# Get subcategories for selected category
cat_index = category_names.index(new_category)
subcat_list = subcategories[cat_index]
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
    new_subcategory = None
```

#### 4. Full Updated Section
**File**: `src/budget_tracker/cli/confirmation.py`
**Lines**: 68-98 (complete replacement)

```python
        elif choice == "n":
            # Let user pick category
            new_category = select_option("\nSelect category", category_names)

            # Get subcategories for selected category
            cat_index = category_names.index(new_category)
            subcat_list = subcategories[cat_index]
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
                new_subcategory = None

            transaction.category = new_category
            transaction.subcategory = new_subcategory
            transaction.confidence = 1.0  # User-confirmed
            # Cache the user's choice
            confirmed_cache[transaction.description] = (new_category, new_subcategory)
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`
- [x] Formatting: `ruff format --check`
- [x] Tests pass: `pytest tests/`

#### Manual Verification:
- [x] Process a CSV with uncertain transactions
- [x] Press 'n' to reject a suggestion
- [x] Verify category selection uses arrow keys
- [x] Verify subcategory selection uses arrow keys
- [x] Verify "(Skip)" option works for subcategory

**Note**: Pause for manual confirmation before marking complete.

---

## Testing Strategy

### Unit Tests:
- Existing `test_selection.py` covers `select_option()` behavior
- May need to update any mocks in `test_mapping.py` if they exist
- May need to update any mocks in `test_confirmation.py` if they exist

### Manual Testing:
1. **mapping.py flow**:
   - Run `budget-tracker process <new_csv>` where no mapping exists
   - Navigate all column selections with arrow keys
   - Select "Other" for currency and date format to test text input fallback

2. **confirmation.py flow**:
   - Process a CSV that generates uncertain categorizations
   - Press 'n' to override suggestion
   - Navigate category/subcategory with arrow keys
   - Test "(Skip)" for subcategory

3. **Fallback testing**:
   - Run with `BUDGET_TRACKER_NO_INTERACTIVE=1` to verify Rich fallback

## Summary of Changes

| File | Menus Migrated | Prompts Unchanged |
|------|----------------|-------------------|
| `mapping.py` | 6 (columns, currency, date format, decimal) | 3 y/n + 3 text input |
| `confirmation.py` | 2 (category, subcategory) | 1 y/n/s |
| `transfer_confirmation.py` | 0 | 1 y/n/a/s |

## References
- Existing selection utility: `src/budget_tracker/cli/selection.py`
- Arrow-key selection plan: `.claude/thoughts/shared/plans/2026-01-17-interactive-arrow-key-selection.md`
- Blacklist migration example: `src/budget_tracker/cli/blacklist.py`
