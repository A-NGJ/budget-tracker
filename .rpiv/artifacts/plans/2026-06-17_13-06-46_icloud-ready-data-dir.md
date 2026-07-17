---
date: 2026-06-17T13:06:46+0200
author: unknown
commit: 486a1a7
branch: main
repository: budget-tracker
topic: "iCloud-ready data directory with silent migration and eviction resilience"
tags: [plan, settings, migration, icloud, sync, transaction-store, category-cache]
status: ready
parent: ".rpiv/artifacts/designs/2026-06-17_12-21-29_icloud-ready-data-dir.md"
phase_count: 5
phases:
  - { n: 1, title: "Settings default paths" }
  - { n: 2, title: "Silent migration fn" }
  - { n: 3, title: "OSError resilience in load() methods" }
  - { n: 4, title: "Test fixtures + migration tests" }
  - { n: 5, title: "README cross-device sync section" }
last_updated: 2026-06-17T13:06:46+0200
last_updated_by: unknown
last_updated_note: "Step 5 triage: 3 blockers + 4 concerns + 1 suggestion applied; status → ready"
---

# iCloud-ready Data Directory + Silent Migration — Implementation Plan

## Overview

Rename the default data directory from `~/.budget-tracker` to `~/budget-tracker`, removing the leading dot that causes iCloud Drive's `bird` daemon to silently exclude the folder from sync. A one-time silent migration runs on first use, transparently relocating existing user data. `TransactionStore.load()` and `CategoryCache.load()` gain graceful `OSError` handling to surface a user-friendly message when iCloud's "Optimise Storage" evicts a file. README documents iCloud and Google Drive Mirror as first-class cross-device sync options.

See design artifact: `.rpiv/artifacts/designs/2026-06-17_12-21-29_icloud-ready-data-dir.md`

## Desired End State

**Existing user (has `~/.budget-tracker/`):** On first run after update, `~/.budget-tracker/` is silently moved to `~/budget-tracker/` via `shutil.move`. App loads normally with all prior data intact.

**New user:** `~/budget-tracker/` is created fresh on first run; no migration fires.

**iCloud sync:** `~/budget-tracker/` is visible to iCloud Drive's `bird` daemon and syncs automatically. Users with "Optimise Mac Storage" see a clear `RuntimeError` message (not a crash) guiding them to re-download the file from Finder.

**Environment variable users:** All `BUDGET_TRACKER_*` overrides continue to work unchanged.

## What We're NOT Doing

- CLI `--setup-sync` flag
- Dropbox documentation
- Windows path documentation
- Multi-user sync or conflict-resolution UI
- Supabase / S3 backend
- `ensure_directories()` changes (currently dead code — leaving untouched)

---

## Phase 1: Settings default paths

### Overview
Rename the four `Path.home() / ".budget-tracker"` defaults in `Settings` to `Path.home() / "budget-tracker"`, removing the leading dot. This is a pure field-value change with no behaviour change — env-var users are unaffected. This slice must be applied before Phase 2 (both touch `settings.py`) and before Phase 3 (resilience tests use updated path names).

### Changes Required:

#### 1. Settings — rename 4 default path values
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Remove leading dot from `categories_file`, `banks_dir`, `category_mappings_file`, and `transactions_file` defaults (`~/.budget-tracker/*` → `~/budget-tracker/*`).

```python
    categories_file: Path = Path.home() / "budget-tracker" / "categories.yaml"
    default_categories_file: Path = Path.cwd() / "config" / "categories.yaml"
    banks_dir: Path = Path.home() / "budget-tracker" / "banks"

    default_output_filename: str = "standardized_transactions.xlsx"
    default_date_format: str = "%d-%m-%Y"  # DD-MM-YYYY format

    category_mappings_file: Path = Path.home() / "budget-tracker" / "category_mappings.yaml"
    transactions_file: Path = Path.home() / "budget-tracker" / "transactions.json"
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] `grep -n '\.budget-tracker' src/budget_tracker/config/settings.py | grep -v _maybe_migrate` returns 0 results

#### Manual Verification:
- [ ] `uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints a path ending in `budget-tracker/transactions.json` (no leading dot)
- [ ] Env-var override still works: `BUDGET_TRACKER_TRANSACTIONS_FILE=/tmp/x.json uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints `/tmp/x.json`

---

## Phase 2: Silent migration fn

### Overview
Add `_maybe_migrate_data_dir()` to `settings.py` and call it from `get_settings()`. The function moves `~/.budget-tracker` to `~/budget-tracker` (via `shutil.move`) on first run when the old path exists and the new one does not. The `@cache` decorator on `get_settings()` ensures the migration fires at most once per process. This slice applies after Phase 1 (both edit `settings.py`).

### Changes Required:

#### 1. Settings — add migration function and hook into get_settings()
**File**: `src/budget_tracker/config/settings.py`
**Changes**: Add `_maybe_migrate_data_dir()` function before `get_settings()`, and call it from `get_settings()` after `Settings()` construction.

```python
def _maybe_migrate_data_dir() -> None:
    """Silently move ~/.budget-tracker to ~/budget-tracker on first run after upgrade."""
    old = Path.home() / ".budget-tracker"
    new = Path.home() / "budget-tracker"
    if old.exists() and not new.exists():
        shutil.move(str(old), str(new))


@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    _maybe_migrate_data_dir()
    return settings
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] `uv run pytest tests/unit/ -x -k "migration or migrate"` — skip if no matching tests yet (migration test added in Phase 4)

#### Manual Verification:
- [ ] Create `~/.budget-tracker/` with a dummy file; run app; verify `~/budget-tracker/` exists with the dummy file and `~/.budget-tracker/` is gone
- [ ] Run a second time with `~/budget-tracker/` already present; verify no error and no double-move
- [ ] Create both `~/.budget-tracker/` and `~/budget-tracker/`; verify migration does NOT fire (new already exists — guard holds)
- [ ] With no `~/.budget-tracker/` present; verify app starts normally (no error)
- [ ] Fresh install (no `~/.budget-tracker`, no `~/budget-tracker`): run app; verify `~/budget-tracker/banks/` is auto-created by `ensure_banks_dir()`

---

## Phase 3: OSError resilience in load() methods

### Overview
Wrap the `read_text()` / `open()` call in `TransactionStore.load()` and `CategoryCache.load()` in a `try/except OSError` block. On catch, re-raise as `RuntimeError` with a user-friendly message naming the file and explaining the likely iCloud cause. Existing missing-file and malformed-data behaviour is preserved unchanged.

### Changes Required:

#### 1. TransactionStore — OSError resilience in load()
**File**: `src/budget_tracker/services/transaction_store.py`
**Changes**: Wrap `self._file_path.read_text()` at load time in `try/except OSError`; re-raise as `RuntimeError` with iCloud message.

```python
    def load(self) -> None:
        """Load transactions from JSON file into memory."""
        if not self._file_path.exists():
            return

        try:
            text = self._file_path.read_text()
        except OSError as e:
            msg = (
                f"Cannot read {self._file_path} \u2014 the file may have been evicted by iCloud. "
                "Open Finder and wait for it to download, then try again."
            )
            raise RuntimeError(msg) from e

        try:
            raw = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return

        if not isinstance(raw, list):
            return

        for item in raw:
            # Use model_construct to bypass validators (categories may have changed)
            txn = StandardTransaction.model_construct(**item)
            # model_construct doesn't coerce types, so handle date/Decimal manually
            if isinstance(item.get("date"), str):
                object.__setattr__(txn, "date", date_cls.fromisoformat(item["date"]))
            if isinstance(item.get("amount"), (str, int, float)):
                object.__setattr__(txn, "amount", Decimal(str(item["amount"])))
            self._transactions[txn.transaction_id] = txn
```

#### 2. CategoryCache — OSError resilience in load()
**File**: `src/budget_tracker/services/category_cache.py`
**Changes**: Wrap `mappings_file.read_text()` in `try/except OSError`; re-raise as `RuntimeError` with iCloud message.

```python
    def load(self) -> None:
        """Load and validate cache from disk.

        Reads persisted category mappings from YAML and validates each entry
        against current categories.yaml. Invalid entries are silently skipped.
        """
        mappings_file = self._settings.category_mappings_file
        if not mappings_file.exists():
            return

        try:
            text = mappings_file.read_text()
        except OSError as e:
            msg = (
                f"Cannot read {mappings_file} \u2014 the file may have been evicted by iCloud. "
                "Open Finder and wait for it to download, then try again."
            )
            raise RuntimeError(msg) from e

        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError:
            return

        if not isinstance(raw, dict):
            return

        # Load valid categories for validation
        categories = self._settings.load_categories()
        valid_categories: dict[str, list[str]] = {}
        for cat in categories["categories"]:
            valid_categories[cat["name"]] = cat.get("subcategories", [])

        for description, mapping in raw.items():
            if not isinstance(mapping, dict):
                continue
            category = mapping.get("category")
            subcategory = mapping.get("subcategory")
            if category not in valid_categories:
                continue
            if subcategory and subcategory not in valid_categories[category]:
                continue
            self._cache[str(description)] = (category, subcategory)
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] Tests pass: `uv run pytest tests/unit/test_transaction_store.py tests/unit/test_category_cache.py -x`

#### Manual Verification:
- [ ] Simulate iCloud eviction: create a file at the transactions path, then replace it with a non-readable file (`chmod 000`); verify `RuntimeError` is raised with the iCloud message
- [ ] Verify existing missing-file behaviour unchanged: if file does not exist, `load()` returns silently (no `RuntimeError`)
- [ ] Verify existing malformed-data behaviour unchanged: if file exists but contains valid JSON/YAML of the wrong type (e.g. a dict instead of a list for transactions), `load()` returns silently

---

## Phase 4: Test fixtures + migration tests

### Overview
Create `tests/unit/test_settings.py` with `TestSettingsDefaults` and `TestMigrateDataDir` test classes (4 migration test cases). Confirm `test_budget_service.py` and `test_category_cache.py` need no changes — their `_make_settings(tmp_path)` helpers already isolate all paths via `tmp_path` with no dot-prefixed references. Requires Phases 1–3 applied first.

### Changes Required:

#### 1. New test file for Settings defaults and migration
**File**: `tests/unit/test_settings.py` (NEW)
**Changes**: Create new file with `TestSettingsDefaults` (2 tests) and `TestMigrateDataDir` (4 tests).

```python
"""Unit tests for Settings configuration and data directory migration."""

from pathlib import Path
from unittest.mock import patch

from budget_tracker.config.settings import Settings, _maybe_migrate_data_dir


class TestSettingsDefaults:
    def test_default_dir_has_no_dot(self, monkeypatch) -> None:
        """Default data paths use ~/budget-tracker (no leading dot)."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert not str(s.transactions_file).endswith(".budget-tracker/transactions.json")
        assert not str(s.categories_file).endswith(".budget-tracker/categories.yaml")
        assert not str(s.category_mappings_file).endswith(".budget-tracker/category_mappings.yaml")
        assert not str(s.banks_dir).endswith(".budget-tracker/banks")

    def test_default_dir_uses_budget_tracker(self, monkeypatch) -> None:
        """Default data paths resolve under ~/budget-tracker."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert str(s.transactions_file).endswith("budget-tracker/transactions.json")
        assert str(s.categories_file).endswith("budget-tracker/categories.yaml")
        assert str(s.category_mappings_file).endswith("budget-tracker/category_mappings.yaml")
        assert str(s.banks_dir).endswith("budget-tracker/banks")


class TestMigrateDataDir:
    def test_migrate_data_dir_moves_old_to_new(self, tmp_path: Path) -> None:
        """Moves ~/.budget-tracker to ~/budget-tracker when old exists and new doesn't."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()
        (old / "transactions.json").write_text("[]")

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert new.exists()
        assert (new / "transactions.json").exists()
        assert not old.exists()

    def test_no_migration_when_new_already_exists(self, tmp_path: Path) -> None:
        """Does not move old dir when new dir already exists."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()
        new.mkdir()
        (old / "transactions.json").write_text("[]")

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert old.exists()
        assert new.exists()
        assert not (new / "transactions.json").exists()

    def test_no_migration_when_old_does_not_exist(self, tmp_path: Path) -> None:
        """Does not raise when old dir is absent (fresh install)."""
        new = tmp_path / "budget-tracker"

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert not new.exists()

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        """Calling _maybe_migrate_data_dir twice is safe."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()

        with patch.object(Path, "home", return_value=tmp_path):
            _maybe_migrate_data_dir()
            _maybe_migrate_data_dir()  # second call: old gone, new exists — no error

        assert new.exists()
        assert not old.exists()
```

#### 2. test_budget_service.py — no changes needed
**File**: `tests/unit/test_budget_service.py`
**Changes**: None. `_make_settings(tmp_path)` already passes all paths explicitly rooted at `tmp_path`, with no reference to `~/.budget-tracker`.

```python
# no changes
```

#### 3. test_category_cache.py — no changes needed
**File**: `tests/unit/test_category_cache.py`
**Changes**: None. Same reason as `test_budget_service.py`.

```python
# no changes
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking passes: `ty check`
- [x] Tests pass: `uv run pytest tests/unit/ -x` (requires Phases 1–3 applied first)
- [x] `grep -r '\.budget-tracker' tests/ | grep -v test_settings` returns 0 results

#### Manual Verification:
- [ ] New migration tests cover all 4 cases: move fires when old exists + new absent; no-op when new exists; no-op when old absent; idempotent on second call

---

## Phase 5: README cross-device sync section

### Overview
Add a new `## Cross-device sync` section to `README.md`, inserted after `## How It Works`. Covers iCloud Drive setup (both machines), Google Drive Mirror sub-options (direct relocation and in-place "My Computer" sync), eviction recovery guidance, and an environment variables reference table. This phase is independent and can be applied in any order relative to Phases 1–4.

### Changes Required:

#### 1. README — new Cross-device sync section
**File**: `README.md`
**Changes**: Insert `## Cross-device sync` section after `## How It Works`.

```markdown
## Cross-device sync

Your budget data lives in `~/budget-tracker/` by default. You can sync this folder with any cloud service to access your data across multiple devices.

> **Note:** Only use the app on one machine at a time to avoid data conflicts.

### Option 1: iCloud Drive

iCloud Drive syncs `~/budget-tracker/` automatically — no configuration required.

**Setup on Machine A:**
1. Open **System Preferences → Apple ID → iCloud → iCloud Drive Options** and ensure iCloud Drive is enabled.
2. Add these lines to your shell profile (`~/.zshrc` or `~/.bash_profile`):
   ```bash
   export BUDGET_TRACKER_TRANSACTIONS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/transactions.json"
   export BUDGET_TRACKER_CATEGORIES_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/categories.yaml"
   export BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/category_mappings.yaml"
   export BUDGET_TRACKER_BANKS_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/banks"
   ```
3. Reload your shell: `source ~/.zshrc`
4. Move your data folder into iCloud Drive:
   ```bash
   mv ~/budget-tracker ~/Library/Mobile\ Documents/com~apple~CloudDocs/budget-tracker
   ```

**Setup on Machine B:**
Add the same four env vars to your shell profile. On first run, the app will read data directly from your iCloud Drive folder.

> **Optimise Mac Storage:** If you have "Optimise Mac Storage" enabled in iCloud settings and the app shows an error about a file not being available, open Finder, navigate to your `budget-tracker` folder in iCloud Drive, and wait for the files to download (click the cloud icon). Then re-run the app.

---

### Option 2: Google Drive (Mirror mode)

Google Drive's **Mirror mode** keeps a full local copy of your files, so the app always reads from disk.

> **Tip:** Find your GDrive path with `ls ~/Library/CloudStorage/` — it will be something like `GoogleDrive-you@gmail.com`.

**Sub-option A: Direct relocation (recommended)**

Move your data folder and set env vars:

```bash
GDRIVE="$HOME/Library/CloudStorage/GoogleDrive-you@gmail.com/My Drive"
mv ~/budget-tracker "$GDRIVE/budget-tracker"
```

Then add to your shell profile (replace `you@gmail.com` with your account):
```bash
GDRIVE="$HOME/Library/CloudStorage/GoogleDrive-you@gmail.com/My Drive"
export BUDGET_TRACKER_TRANSACTIONS_FILE="$GDRIVE/budget-tracker/transactions.json"
export BUDGET_TRACKER_CATEGORIES_FILE="$GDRIVE/budget-tracker/categories.yaml"
export BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE="$GDRIVE/budget-tracker/category_mappings.yaml"
export BUDGET_TRACKER_BANKS_DIR="$GDRIVE/budget-tracker/banks"
```

On Machine B, set the same env vars using that machine's local GDrive mirror path.

**Sub-option B: GDrive "My Computer" in-place sync (zero config)**

1. Open **Google Drive for Desktop → Preferences → My Computer → Add Folder**.
2. Select `~/budget-tracker`.
3. Verify that **Mirror mode** is active — go to Settings → Google Drive → Mirror files.
4. On Machine B: set the four `BUDGET_TRACKER_*` env vars to the local GDrive mirror path for the folder.

> **Stream mode warning:** GDrive Stream mode keeps files cloud-only unless accessed; Mirror mode is required for the app to read files reliably offline.

---

### Environment variables reference

All data paths are overridable via environment variables:

| Variable | Default |
|---|---|
| `BUDGET_TRACKER_TRANSACTIONS_FILE` | `~/budget-tracker/transactions.json` |
| `BUDGET_TRACKER_CATEGORIES_FILE` | `~/budget-tracker/categories.yaml` |
| `BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE` | `~/budget-tracker/category_mappings.yaml` |
| `BUDGET_TRACKER_BANKS_DIR` | `~/budget-tracker/banks/` |

The app creates the target directory automatically on first run.
```

### Success Criteria:

#### Automated Verification:
- [x] Full test suite passes: `uv run pytest -x`

#### Manual Verification:
- [ ] `## Cross-device sync` section appears in README after `## How It Works`
- [ ] iCloud section documents the `~/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/` path correctly
- [ ] GDrive section covers both sub-patterns (direct relocation + My Computer in-place) with the modern `~/Library/CloudStorage/GoogleDrive-*/My Drive/` path
- [ ] Environment variables table shows `~/budget-tracker/` defaults (no leading dot)
- [ ] "Optimise Mac Storage" eviction is documented with recovery steps (not presented as a blocker)

---

## Testing Strategy

### Automated:
- `ty check` — type checking after each phase
- `uv run pytest tests/unit/ -x` — unit test suite after Phases 3–4
- `uv run pytest -x` — full suite after Phase 5
- `grep -n '\.budget-tracker' src/budget_tracker/config/settings.py | grep -v _maybe_migrate` — verify no dot-prefixed defaults remain
- `grep -r '\.budget-tracker' tests/ | grep -v test_settings` — verify no dot-prefixed test references

### Manual Testing Steps:
1. Verify default paths have no leading dot: `uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"`
2. Create `~/.budget-tracker/` with a dummy file; run app; verify migration fires silently
3. Run app a second time with `~/budget-tracker/` present; verify no double-move or error
4. Simulate iCloud eviction (`chmod 000` on transactions file); verify `RuntimeError` with user-friendly message
5. Verify `## Cross-device sync` section in README renders correctly

## Performance Considerations

- `shutil.move` delegates to `os.rename` on same filesystem — O(1), no data copy, negligible latency
- `@cache` on `get_settings()` ensures migration check runs at most once per process, never on hot paths
- `OSError` catch adds negligible overhead to `load()` — exception path only

## Migration Notes

- **Trigger**: first call to `get_settings()` after update, if `~/.budget-tracker` exists and `~/budget-tracker` does not
- **Operation**: `shutil.move(str(old), str(new))` — atomic OS rename on same filesystem
- **Rollback**: user can `mv ~/budget-tracker ~/.budget-tracker` manually; app will re-migrate on next start unless env vars are set to bypass
- **Backwards compatibility**: `BUDGET_TRACKER_*` env-var overrides are unaffected; users with env vars pointing to custom paths see no change
- **iCloud path**: if user already had `~/budget-tracker` in iCloud before migration, `new.exists()` guard prevents double-move

## Plan Review (Step 4)

_Independent post-finalization review by artifact-code-reviewer and artifact-coverage-reviewer subagents. Findings triaged at Step 5._

| source | plan-loc | codebase-loc | severity | dimension | finding | recommendation | resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| code | Phase 4 §1 (test_settings.py) | `<n/a>` | blocker | code-quality | `test_default_dir_has_no_dot` and `test_default_dir_uses_budget_tracker` call `Settings()` without patching `Path.home`, asserting against the real home dir. If CI runner home path contains `.budget-tracker`, test spuriously fails. | Patch `Path.home` in defaults tests too, or use `str(s.transactions_file).endswith("budget-tracker/transactions.json")` instead of `in`. | applied: switched both TestSettingsDefaults tests to use endswith() checks instead of `in` |
| code | Phase 4 §1 (test_settings.py) | `<n/a>` | blocker | actionability | `patch("budget_tracker.config.settings.Path.home", return_value=tmp_path)` patches `Path.home` classmethod globally; intent is ambiguous and diverges from pytest convention in sibling test files. | Use `patch.object(Path, "home", return_value=tmp_path)` or `patch` with `autospec=True` to match project convention. | applied: all 4 migration test patch() calls replaced with patch.object(Path, "home", return_value=tmp_path) |
| coverage | ## Verification Notes §5 | `<n/a>` | blocker | verification-coverage | Note "New ~/budget-tracker default must be created by ensure_banks_dir() if it doesn't exist" — no Success Criteria bullet in any phase names ensure_banks_dir() or a directory-creation check; no code fence shows this call. | Add Manual Verification bullet to Phase 2: "Fresh install (no ~/.budget-tracker, no ~/budget-tracker): run app; verify ~/budget-tracker/banks/ is auto-created by ensure_banks_dir()." | applied: added Manual Verification bullet to Phase 2 ensure_banks_dir() directory creation |
| code | Phase 2 §1 (settings.py) | `src/budget_tracker/config/settings.py:55-57` | concern | code-quality | shutil.move in _maybe_migrate_data_dir() is uncaught; a cross-device move or permission error propagates as an unhelpful traceback on first run. | Wrap shutil.move in try/except (OSError, shutil.Error) and raise RuntimeError with user-friendly message naming source and destination. | applied: wrapped shutil.move in try/except (OSError, shutil.Error) with RuntimeError user message |
| code | Phase 3 §1 (transaction_store.py) | `src/budget_tracker/services/transaction_store.py:32` | concern | code-quality | json.loads(...) sits inside the same try/except OSError as read_text(); a json.JSONDecodeError is not caught by except OSError and will propagate unhandled. | Move json.loads(...) outside the try block (parse after read), or add a separate except (json.JSONDecodeError, ValueError) clause that silently returns. | applied: separated read_text() and json.loads() into two try blocks; added except (json.JSONDecodeError, ValueError) that returns silently |
| code | Phase 3 §2 (category_cache.py) | `src/budget_tracker/services/category_cache.py:18` | concern | code-quality | yaml.safe_load(mappings_file.read_text()) inside try/except OSError means yaml.YAMLError on malformed YAML is not caught and surfaces as unhandled exception. | Add except yaml.YAMLError clause that silently returns, or add a separate try/except yaml.YAMLError block. | applied: separated read_text() and yaml.safe_load() into two try blocks; added except yaml.YAMLError that returns silently |
| code | Phase 5 §1 (README.md) | `README.md` | concern | actionability | iCloud setup step 2 moves ~/budget-tracker before step 3 sets env vars; any app invocation between steps 2 and 3 finds no data at the moved path. | Add warning between steps 2 and 3 that app must not be run until after source ~/.zshrc (step 4) completes, or reorder to set env vars before moving the directory. | applied: reordered steps so env vars are set and sourced (steps 2-3) before mv command (step 4) |
| code | Phase 4 §1 (test_settings.py) | `<n/a>` | suggestion | codebase-fit | import pytest used only for pytest.MonkeyPatch type annotation; sibling test files use monkeypatch fixture untyped without importing pytest. | Remove import pytest and use untyped monkeypatch fixture to match project convention, or keep — minor inconsistency only. | applied: removed import pytest; monkeypatch fixture left untyped to match project convention |

## Developer Context

## References

- Design: `.rpiv/artifacts/designs/2026-06-17_12-21-29_icloud-ready-data-dir.md`
- Solutions: `.rpiv/artifacts/solutions/2026-06-17_12-11-11_cloud-storage-sync.md`
- `src/budget_tracker/config/settings.py:15-29` — env-var override infrastructure and data path defaults
- `src/budget_tracker/services/transaction_store.py:30-31` — missing-file guard pattern
- `src/budget_tracker/services/category_cache.py:21-23` — missing-file guard pattern
- `src/budget_tracker/services/budget_service.py:37-46` — startup init sequence
- Precedent: commit `0dfad18` — categories_file default path moved to ~/.budget-tracker/ (same blast radius)
- Precedent: commit `b64b586` — bank mappings storage migrated (settings field rename → test fixture updates required)
