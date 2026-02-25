---
date: 2026-02-25T21:14:21Z
researcher: Claude
git_commit: 4cb818606d680754720cbb8eb126fabf9345d5c0
branch: main
repository: budget-tracker
topic: "What is needed to remove LLM guessing of categories, instead they should be picked by a user"
tags: [research, codebase, categorization, llm, user-selection, categories]
status: complete
last_updated: 2026-02-25
last_updated_by: Claude
---

# Research: Removing LLM Category Guessing in Favor of User Selection

**Date**: 2026-02-25T21:14:21Z
**Researcher**: Claude
**Git Commit**: 4cb818606d680754720cbb8eb126fabf9345d5c0
**Branch**: main
**Repository**: budget-tracker

## Research Question

What is needed to remove LLM guessing of categories, instead they should be picked by a user?

## Summary

The current system sends every non-transfer transaction description to a local Ollama LLM (Mistral model) which returns a JSON object with `category`, `subcategory`, and `confidence`. Transactions with confidence below 0.6 are then shown to the user for confirmation. To replace LLM guessing with direct user selection, the changes touch four areas: (1) the main CLI pipeline orchestration, (2) the categorization invocation and `CategoryResult`/`LLMCategorizer` module, (3) the confirmation UI which already contains a working category selection UI, and (4) the Ollama dependency check. The existing `select_option()` UI and `categories.yaml` loading infrastructure can be reused directly.

## Detailed Findings

### 1. Where the LLM Is Currently Invoked

The LLM categorization is called in the `process` command at `src/budget_tracker/cli/main.py:170-193`. The relevant section:

- **Line 143**: `categorizer = LLMCategorizer(_settings)` -- the categorizer is instantiated.
- **Line 170-172**: For each transaction in `transactions_to_categorize`, `categorizer.categorize(parsed.description)` is called, returning a `CategoryResult` with `category`, `subcategory`, and `confidence`.
- **Lines 183-193**: A `StandardTransaction` is constructed using the LLM-provided category, subcategory, and confidence.

This loop processes every non-transfer transaction sequentially through the LLM before any user interaction occurs.

### 2. The Ollama Dependency Check

At `main.py:71-75`, the CLI checks if Ollama is running via `is_ollama_running()` (from `src/budget_tracker/utils/ollama.py:4-12`), which runs `pgrep -f "ollama serve"`. If Ollama is not running, the entire `process` command exits with code 1. This gate would need to be removed or made conditional.

### 3. The Existing User Category Selection UI

A fully functional category selection UI already exists in `src/budget_tracker/cli/confirmation.py:69-94`. When a user chooses to override an LLM suggestion (pressing `n`), the flow is:

1. `select_option("\nSelect category", category_names)` -- presents all 13 categories from `categories.yaml` via arrow-key navigation (`questionary.select`) or numbered fallback.
2. If the selected category has subcategories, `select_option(f"Select subcategory for {new_category}", subcat_choices)` is called, with a `"(Skip)"` option appended.
3. The transaction's `category`, `subcategory`, and `confidence` (set to 1.0) are updated directly.

Categories are loaded from `categories.yaml` via `settings.load_categories()` at `confirmation.py:31-33`, which extracts `category_names` and positionally-aligned `subcategories` lists.

### 4. The Confirmation Flow and Its Threshold

The `confirm_uncertain_categories()` function at `confirmation.py:11-101`:

- Filters transactions where `confidence < 0.6` (hard-coded at line 24).
- For each uncertain transaction, shows description + amount + LLM suggestion, and prompts `y/n/s` (accept/override/skip).
- Maintains a `confirmed_cache` (dict keyed by `description`) so duplicate descriptions are auto-resolved.

If the LLM is removed, this function's role changes fundamentally -- instead of reviewing uncertain LLM guesses, it becomes the primary categorization mechanism for every transaction.

### 5. The Description Caching Pattern

The `confirmed_cache` at `confirmation.py:36` maps `transaction.description -> (category, subcategory)`. When the same description appears again, the cached category is applied automatically with confidence 1.0 (lines 44-51). This pattern is directly reusable for user-driven categorization -- once a user categorizes "Netto" as "Food & Drinks / Groceries", all subsequent "Netto" transactions get the same category without re-prompting.

### 6. The CategoryResult and LLMCategorizer Modules

**`CategoryResult`** (`src/budget_tracker/categorizer/llm_categorizer.py:10-87`): A Pydantic model with `category`, `subcategory`, `confidence`, `needs_confirmation`. Has validators that check category/subcategory against `categories.yaml`. The `__init__` sets `needs_confirmation=True` if confidence is below the threshold (default 0.9).

**`LLMCategorizer`** (`llm_categorizer.py:89-205`): Contains `categorize()`, `categorize_batch()`, `_build_prompt()`, `_format_categories()`, `_parse_response()`. All methods are LLM-specific. The prompt includes hardcoded supermarket names (Netto, Lidl, Rema 1000, etc.) and few-shot examples for Danish vendors.

### 7. The StandardTransaction Model

`StandardTransaction` at `src/budget_tracker/models/transaction.py:13-95`:
- `category: str` (required, validated against `categories.yaml`)
- `subcategory: str | None = None` (validated under parent category)
- `confidence: float = 1.0` (constrained to [0.0, 1.0])
- `frozen=False` -- allows in-place mutation of fields

The `confidence` field currently serves two purposes: (1) tracking LLM certainty, and (2) flagging transactions for user review. With user-driven categorization, all transactions would have confidence 1.0.

### 8. The categories.yaml File

Located at `config/categories.yaml`, contains 13 categories with subcategories:

| Category | Subcategory Count |
|---|---|
| Food & Drinks | 4 |
| Shopping | 8 |
| Housing | 6 |
| Transportation | 4 |
| Car | 5 |
| Life & Entertainment | 8 |
| Healthcare | 4 |
| Communication & PC | 3 |
| Financial expenses | 4 |
| Investments | 1 |
| Income | 4 |
| Other | 1 |
| Internal Transfer | 1 |

This file is the single source of truth, loaded at multiple points: `LLMCategorizer.__init__`, `CategoryResult` validators, `StandardTransaction` validators, and `confirm_uncertain_categories()`.

### 9. Downstream Consumers of Categories

Categories flow through the pipeline to three outputs:

- **CSV export** (`src/budget_tracker/exporters/csv_exporter.py:33-34`): Writes `t.category` and `t.subcategory` as columns.
- **Google Sheets export** (`src/budget_tracker/exporters/google_sheets_exporter.py:52-53`): Writes category at row index 3, subcategory at index 4.
- **Summary** (`src/budget_tracker/exporters/summary.py:18-22`): Groups expenses by `t.category` for the totals table.

None of these care how the category was assigned -- they just read the `StandardTransaction` fields. No changes needed here.

### 10. The Transfer Detection Bypass

Confirmed internal transfers at `main.py:149-167` are hardcoded to `category="Internal Transfer"`, `subcategory="Transfer"`, `confidence=1.0`. This bypasses the LLM entirely and would remain unchanged.

### 11. Settings Related to LLM

In `src/budget_tracker/config/settings.py`:
- `ollama_base_url: str = "http://localhost:11434"` (line 23)
- `ollama_model: str = "mistral"` (line 24)
- `ollama_confidence_threshold: float = 0.9` (line 25)

These three settings become unused if the LLM categorizer is removed.

### 12. Test Impact

Tests that reference categorization:

| File | What It Tests | Impact |
|---|---|---|
| `tests/unit/test_categorizer.py` | LLM categorizer directly (4 tests) | Would be removed or replaced entirely |
| `tests/unit/test_models.py:39-74` | Category validation on `StandardTransaction` | Unchanged -- validation stays |
| `tests/integration/test_cli.py:126-215` | Full pipeline with mocked `LLMCategorizer` | Mock target changes from `LLMCategorizer` to whatever replaces it |
| `tests/integration/test_cli_sheets.py` | Pipeline with sheets export, mocked categorizer | Same as above |

## Code References

- `src/budget_tracker/cli/main.py:71-75` -- Ollama running check (gate to remove)
- `src/budget_tracker/cli/main.py:143` -- `LLMCategorizer` instantiation
- `src/budget_tracker/cli/main.py:170-193` -- LLM categorization loop (main replacement target)
- `src/budget_tracker/cli/confirmation.py:11-101` -- Uncertain category confirmation (contains reusable selection UI)
- `src/budget_tracker/cli/confirmation.py:36` -- Description caching dict (reusable pattern)
- `src/budget_tracker/cli/confirmation.py:69-94` -- Category/subcategory selection via `select_option()` (existing UI to reuse)
- `src/budget_tracker/cli/selection.py:36-67` -- `select_option()` function (arrow-key or numbered selection)
- `src/budget_tracker/categorizer/llm_categorizer.py:10-87` -- `CategoryResult` model
- `src/budget_tracker/categorizer/llm_categorizer.py:89-205` -- `LLMCategorizer` class
- `src/budget_tracker/utils/ollama.py:4-12` -- `is_ollama_running()` utility
- `src/budget_tracker/config/settings.py:23-25` -- Ollama-related settings
- `src/budget_tracker/models/transaction.py:13-95` -- `StandardTransaction` model
- `config/categories.yaml:1-93` -- Category definitions

## Architecture Documentation

### Current Categorization Pipeline
```
ParsedTransaction (no category)
  |
  v
LLMCategorizer.categorize(description)  -->  CategoryResult
  |
  v
StandardTransaction(category=result.category, ...)
  |
  v
confirm_uncertain_categories()  [only if confidence < 0.6]
  |  User can: accept / override / skip
  v
Final StandardTransaction (exported)
```

### Components Involved in Category Assignment

1. **Category source**: `config/categories.yaml` (13 categories)
2. **Category assigner**: `LLMCategorizer` (Ollama/Mistral)
3. **Category validator**: Pydantic validators on `CategoryResult` and `StandardTransaction`
4. **Category reviewer**: `confirm_uncertain_categories()` in `confirmation.py`
5. **Category selector UI**: `select_option()` in `selection.py`
6. **Category consumers**: CSV exporter, Google Sheets exporter, summary printer

### Key Interfaces Between Components

- `LLMCategorizer.categorize(description: str) -> CategoryResult` -- the interface that would be replaced
- `confirm_uncertain_categories(settings, transactions) -> list[StandardTransaction]` -- the review step that would become the primary categorization step
- `select_option(message, choices, default, allow_back) -> str | None` -- the UI primitive, already working
- `settings.load_categories() -> dict` -- category loading, already used by the confirmation UI

## Historical Context (from .thoughts/)

- `.claude/thoughts/plans/2025-10-10-bank-statement-normalizer-cli.md` -- Original plan that established the LLM categorization architecture (Phase 4) and user confirmation flow (Phase 6).
- `.claude/thoughts/shared/plans/2026-01-08-internal-transfer-detection.md` -- Added the "Internal Transfer" category, established the pattern of bypassing LLM for certain transaction types.
- `.claude/thoughts/shared/plans/2026-01-19-migrate-remaining-menus-to-arrow-key.md` -- Migrated category/subcategory selection in `confirmation.py` from numbered lists to `select_option()` with arrow-key navigation.
- `.claude/thoughts/research/2025-10-14-general-codebase-functions.md` -- Documents the LLM categorization system, CategoryResult model, and confirmation UI in detail.

## Related Research

- `.claude/thoughts/shared/research/2026-01-02-bank-mapping-config-format-extension.md` -- Documents `categories.yaml` as part of the config system.
- `.claude/thoughts/shared/research/2026-01-02-google-sheets-integration-research.md` -- Documents how categories flow to export.

## Open Questions

1. **Persistence of user category choices**: Currently the `confirmed_cache` in `confirmation.py` is in-memory only (per-run). Should user category assignments be persisted to disk so that recurring merchants (e.g., "Netto") are auto-categorized in future runs without re-prompting?
Good idea, can be implemented.
2. **Batch vs. per-transaction UI**: Should the user categorize each transaction one-by-one (current confirmation UI pattern), or should there be a batch view (e.g., table of uncategorized transactions)?
One by one for now
3. **The `confidence` field**: With user-driven categorization, all transactions would have confidence 1.0. Should the field be kept for compatibility, or removed/repurposed?
Should be removed.
4. **LLM as optional**: Should the LLM be removed entirely, or made optional (e.g., a `--no-llm` flag) so users can choose between AI-assisted and manual categorization?
Removed entirely
