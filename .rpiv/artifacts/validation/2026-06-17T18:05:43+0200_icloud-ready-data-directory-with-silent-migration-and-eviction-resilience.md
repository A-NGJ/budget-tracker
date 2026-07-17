---
date: 2026-06-17T18:05:43+0200
author: unknown
commit: 486a1a7
branch: main
repository: budget-tracker
topic: "Validation of iCloud-ready data directory with silent migration and eviction resilience"
status: ready
verdict: pass
parent: ".rpiv/artifacts/plans/2026-06-17_13-06-46_icloud-ready-data-dir.md"
tags: [validation, settings, migration, icloud, sync, transaction-store, category-cache]
last_updated: 2026-06-17T18:05:43+0200
---

## Validation Report: iCloud-ready data directory with silent migration and eviction resilience

### Implementation Status

- ✓ Phase 1: Settings default paths — Fully implemented
- ✓ Phase 2: Silent migration fn — Fully implemented
- ✓ Phase 3: OSError resilience in load() methods — Fully implemented
- ✓ Phase 4: Test fixtures + migration tests — Fully implemented
- ✓ Phase 5: README cross-device sync section — Fully implemented

### Automated Verification Results

- ✓ Type checking: `ty check` — 27 diagnostics, all pre-existing `unresolved-attribute` errors on chart types in unrelated files; no new errors introduced by plan files
- ✓ No dot-prefixed defaults: `grep -n '\.budget-tracker' src/budget_tracker/config/settings.py | grep -v _maybe_migrate` — 0 results (only occurrences reference the old path inside `_maybe_migrate_data_dir`, as expected)
- ✓ Migration tests: `uv run pytest tests/unit/ -x -k "migration or migrate"` — 4 passed
- ✓ Transaction store + category cache tests: `uv run pytest tests/unit/test_transaction_store.py tests/unit/test_category_cache.py -x` — 40 passed
- ✓ Unit suite: `uv run pytest tests/unit/ -x` — 163 passed
- ✓ Full suite: `uv run pytest -x` — 270 passed
- ✓ No dot-prefixed test references: `grep -r '\.budget-tracker' tests/ | grep -v test_settings` — 0 results
- ✓ No regressions detected

### Code Review Findings

#### Matches Plan:

- `settings.py:22–29` — all 4 defaults (`categories_file`, `banks_dir`, `category_mappings_file`, `transactions_file`) use `Path.home() / "budget-tracker"` with no leading dot
- `settings.py:57–70` — `_maybe_migrate_data_dir()` correctly guards with `old.exists() and not new.exists()`, wraps `shutil.move` in `try/except (OSError, shutil.Error)`, re-raises as `RuntimeError` with user-friendly message naming both source and destination paths
- `settings.py:73–77` — `get_settings()` calls `_maybe_migrate_data_dir()` after `Settings()` construction, within the `@cache`-decorated function
- `transaction_store.py:35–46` — `load()` uses two independent `try/except` blocks: first for `read_text()` → `OSError` re-raised as `RuntimeError` with iCloud message, second for `json.loads()` → `(JSONDecodeError, ValueError)` silently returns
- `category_cache.py:26–37` — `load()` uses two independent `try/except` blocks: first for `read_text()` → `OSError` re-raised as `RuntimeError` with iCloud message, second for `yaml.safe_load()` → `yaml.YAMLError` silently returns
- `test_settings.py:7–29` — `TestSettingsDefaults` has 2 tests using `endswith()` assertions and `monkeypatch.delenv()` for all 4 env vars; no `import pytest`
- `test_settings.py:32–88` — `TestMigrateDataDir` has 4 tests, all using `patch.object(Path, "home", return_value=tmp_path)`
- `README.md:50` — `## Cross-device sync` section present with iCloud setup, Google Drive Mirror (both sub-options), eviction recovery guidance, and env vars reference table

#### Deviations from Plan:

- `README.md:50` — `## Cross-device sync` was inserted before `## How It Works` (line 132) rather than after it. The plan specifies "inserted after `## How It Works`". The section is functionally complete and user-facing content is correct; this is a positional deviation in section ordering only, not a content gap.

#### Pattern Conformance:

- ✓ `test_settings.py` — `monkeypatch` untyped, no `import pytest`, `tmp_path: Path` typed with `-> None` annotations: all match the universal pattern across the 13-file test suite
- ✓ `_maybe_migrate_data_dir` — underscore-prefixed private function with docstring and `-> None` annotation, consistent with every private helper in the codebase
- ✓ `shutil` import — pre-existing at `settings.py:3`, already used by `load_categories()` at line 43; `_maybe_migrate_data_dir` does not introduce a new dependency
- ✓ Two-phase `try/except` in `load()` — identical pattern in both `transaction_store.py` and `category_cache.py`: `OSError → RuntimeError` then parse-error → silent return; iCloud message template is verbatim match across both services

### Manual Testing Required:

1. Default path verification:
   - [ ] `uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints a path ending in `budget-tracker/transactions.json` (no leading dot)
   - [ ] `BUDGET_TRACKER_TRANSACTIONS_FILE=/tmp/x.json uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints `/tmp/x.json`

2. Migration smoke test:
   - [ ] Create `~/.budget-tracker/` with a dummy file; run app; verify `~/budget-tracker/` exists with the dummy file and `~/.budget-tracker/` is gone
   - [ ] Run a second time with `~/budget-tracker/` already present; verify no error and no double-move
   - [ ] Create both `~/.budget-tracker/` and `~/budget-tracker/`; verify migration does NOT fire
   - [ ] Fresh install (no `~/.budget-tracker`, no `~/budget-tracker`): run app; verify `~/budget-tracker/banks/` is auto-created by `ensure_banks_dir()`

3. iCloud eviction simulation:
   - [ ] Create a file at the transactions path, replace with `chmod 000` file; verify `RuntimeError` is raised with the iCloud message
   - [ ] Verify existing missing-file behaviour unchanged: if file does not exist, `load()` returns silently
   - [ ] Verify existing malformed-data behaviour unchanged: if file contains wrong-type JSON/YAML, `load()` returns silently

4. README:
   - [ ] `## Cross-device sync` section appears in README and renders correctly
   - [ ] iCloud section documents the `~/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/` path correctly with env vars set before `mv` command
   - [ ] GDrive section covers both sub-patterns with `~/Library/CloudStorage/GoogleDrive-*/My Drive/` path
   - [ ] Environment variables table shows `~/budget-tracker/` defaults (no leading dot)
   - [ ] "Optimise Mac Storage" eviction is documented with recovery steps

### Recommendations:

- The positional deviation in README (Cross-device sync placed before rather than after `## How It Works`) is acceptable — the content is complete and the user experience is unaffected. No action required before commit.
- Ready to commit — implementation is complete and validated.
