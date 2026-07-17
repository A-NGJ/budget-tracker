---
date: 2026-06-17T12:21:29+0200
author: unknown
commit: 486a1a7
branch: main
repository: budget-tracker
topic: "iCloud-ready data directory with silent migration and eviction resilience"
tags: [design, settings, migration, icloud, sync, transaction-store, category-cache]
status: ready
parent: .rpiv/artifacts/solutions/2026-06-17_12-11-11_cloud-storage-sync.md
last_updated: 2026-06-17T12:21:29+0200
last_updated_by: unknown
---

# Design: iCloud-ready Data Directory + Silent Migration

## Summary

Rename the default data directory from `~/.budget-tracker` to `~/budget-tracker`, removing the leading dot that causes iCloud Drive's `bird` daemon to silently exclude the folder from sync. A one-time silent migration via `shutil.move` runs in `get_settings()` on first use, transparently relocating existing user data. `TransactionStore.load()` and `CategoryCache.load()` gain graceful `OSError` handling to surface a user-friendly message when iCloud's "Optimise Storage" evicts a file, rather than crashing. README documents iCloud and Google Drive Mirror as first-class cross-device sync options.

## Requirements

- iCloud Drive syncs the data directory without requiring user config changes after migration
- Existing users with data at `~/.budget-tracker` are migrated silently on first run — no data loss, no user action required
- App handles iCloud "Optimise Storage" file eviction gracefully (user-friendly message, not a crash)
- README documents iCloud and Google Drive Mirror setup as first-class options with no caveats
- `BUDGET_TRACKER_*` env-var overrides continue to work as before
- All existing tests pass after the change; new migration test added

## Current State Analysis

### Key Discoveries

- `settings.py:21-29` — four `Path.home() / ".budget-tracker" / *` defaults; these are the only occurrences of `~/.budget-tracker` outside of settings (`grep` confirmed by solutions research)
- `settings.py:15` — `env_prefix="BUDGET_TRACKER_"` makes all four paths env-var overridable today; env-var users are unaffected by default rename
- `settings.py:56-58` — `get_settings()` is `@cache`-decorated; body runs exactly once per process; safest migration insertion point (before any consumer touches a path)
- `budget_service.py:37-46` — `BudgetService.__init__` calls `ensure_banks_dir()` then `CategoryCache.load()` then `TransactionStore.load()`; migration must precede all of these
- `transaction_store.py:30-31` — `load()` guards only for missing file (`if not self._file_path.exists(): return`); no `OSError` handling; iCloud eviction produces an `OSError` (file appears to exist as a placeholder but is cloud-only)
- `category_cache.py:21-23` — same pattern; same gap
- `settings.py:41-43` — `shutil.copy2` seed-on-first-run pattern for `categories.yaml`; template for migration guard structure
- `test_budget_service.py:16-44` — `_make_settings(tmp_path)` helper; passes `transactions_file` explicitly — already isolated
- `test_category_cache.py:11-37` — `_make_settings(tmp_path)` helper; does NOT pass `transactions_file` — inert but should be consistent
- `test_exporter.py:7,42` — uses `get_settings()` directly; real `Settings()` constructed but home paths never exercised by exporter logic

### Constraints

- Migration must be idempotent (safe to run every boot — guard: `old.exists() and not new.exists()`)
- `shutil.move` is atomic (OS rename) on same filesystem; safe for production data
- `@cache` on `get_settings()` ensures migration runs exactly once per process

## Scope

### Building

- Rename 4 `Settings` path defaults: `~/.budget-tracker/*` → `~/budget-tracker/*`
- `_maybe_migrate_data_dir()` function in `settings.py` called from `get_settings()`
- `OSError` resilience in `TransactionStore.load()` — catch + re-raise as `RuntimeError` with user message
- `OSError` resilience in `CategoryCache.load()` — same pattern
- Verify `_make_settings()` helpers in `test_budget_service.py` and `test_category_cache.py` need no changes (both already pass all paths via `tmp_path`, no dot-prefixed refs)
- New test file `tests/unit/test_settings.py`: `TestSettingsDefaults` (verify no-dot defaults with env-var isolation), `TestMigrateDataDir` with `test_migrate_data_dir_moves_old_to_new` and 3 companion cases
- README `## Cross-device sync` section: iCloud Drive + Google Drive Mirror

### Not Building

- CLI `--setup-sync` flag
- Dropbox documentation
- Windows path documentation
- Multi-user sync or conflict-resolution UI
- Supabase / S3 backend
- `ensure_directories()` (currently dead code — leaving untouched)

## Decisions

### Default directory name: `~/budget-tracker` (no dot)

**Ambiguity**: `~/.budget-tracker` uses the Unix dotfile convention for hidden per-user data dirs; removing the dot makes it visible in Finder/home directory.

**Decision**: Rename to `~/budget-tracker`. iCloud's `bird` daemon excludes dot-prefixed directories by design. The visibility trade-off is acceptable — budget data is not system config, and visibility helps users find/backup their data. `BUDGET_TRACKER_*` env-var users are unaffected.

Evidence: `settings.py:21-29`, solutions artifact iCloud caveat section.

### Migration hook: `get_settings()` after `Settings()` construction

**Decision**: Place `_maybe_migrate_data_dir()` inside `get_settings()` (`settings.py:56-58`), after `Settings()` construction but before `return settings`. This is the only point that:
1. Runs exactly once (`@cache`)
2. Runs before `BudgetService.__init__` touches any path (`budget_service.py:37-46`)
3. Is independent of TUI vs CLI entry point

Evidence: `settings.py:56-58`, `budget_service.py:37-46`, codebase-analyzer findings.

### Migration primitive: `shutil.move`

**Decision**: Use `shutil.move(str(old), str(new))` over `shutil.copy2` + `unlink`. For a full directory rename on the same filesystem, `shutil.move` delegates to `os.rename` (atomic). `shutil.copy2` is appropriate for single-file seeding; `shutil.move` is appropriate for directory relocation.

Evidence: developer decision at Step 4 directional confirm.

### OSError resilience: raise `RuntimeError` with user-visible message

**Decision**: In `TransactionStore.load()` and `CategoryCache.load()`, wrap the `read_text()` / `open()` call in a `try/except OSError` block. Re-raise as `RuntimeError` with a message that names the file and explains the likely iCloud cause. Callers (screens) already catch broad exceptions and show TUI notifications via `self.notify()`.

Evidence: `transaction_store.py:32`, `category_cache.py:21`, TUI error-notification pattern from `tui/screens/*.py`.

## Architecture

### src/budget_tracker/config/settings.py — MODIFY

Modified fields at `settings.py:21-29` — remove leading dot from four default path values. New `_maybe_migrate_data_dir()` function before `get_settings()`, and modified `get_settings()` body.

```python
    categories_file: Path = Path.home() / "budget-tracker" / "categories.yaml"
    default_categories_file: Path = Path.cwd() / "config" / "categories.yaml"
    banks_dir: Path = Path.home() / "budget-tracker" / "banks"

    default_output_filename: str = "standardized_transactions.xlsx"
    default_date_format: str = "%d-%m-%Y"  # DD-MM-YYYY format

    category_mappings_file: Path = Path.home() / "budget-tracker" / "category_mappings.yaml"
    transactions_file: Path = Path.home() / "budget-tracker" / "transactions.json"


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

### src/budget_tracker/services/transaction_store.py — MODIFY

Modified `load()` at `transaction_store.py:25-39` — wrap `read_text()` in `try/except OSError`.

```python
    def load(self) -> None:
        """Load transactions from JSON file into memory."""
        if not self._file_path.exists():
            return

        try:
            raw = json.loads(self._file_path.read_text())
        except OSError as e:
            msg = (
                f"Cannot read {self._file_path} \u2014 the file may have been evicted by iCloud. "
                "Open Finder and wait for it to download, then try again."
            )
            raise RuntimeError(msg) from e

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

### src/budget_tracker/services/category_cache.py — MODIFY

Modified `load()` at `category_cache.py:16-45` — wrap `read_text()` in `try/except OSError`.

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
            raw = yaml.safe_load(mappings_file.read_text())
        except OSError as e:
            msg = (
                f"Cannot read {mappings_file} \u2014 the file may have been evicted by iCloud. "
                "Open Finder and wait for it to download, then try again."
            )
            raise RuntimeError(msg) from e

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

### tests/unit/test_budget_service.py — MODIFY

No changes needed. `_make_settings(tmp_path)` already passes all paths explicitly rooted at `tmp_path`, with no reference to `~/.budget-tracker`. Commitment satisfied by absence.

```python
# no changes
```

### tests/unit/test_category_cache.py — MODIFY

No changes needed for the same reason.

```python
# no changes
```

### tests/unit/test_settings.py — NEW

New test file for Settings defaults and migration function.

```python
"""Unit tests for Settings configuration and data directory migration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from budget_tracker.config.settings import Settings, _maybe_migrate_data_dir


class TestSettingsDefaults:
    def test_default_dir_has_no_dot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default data paths use ~/budget-tracker (no leading dot)."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert ".budget-tracker" not in str(s.transactions_file)
        assert ".budget-tracker" not in str(s.categories_file)
        assert ".budget-tracker" not in str(s.category_mappings_file)
        assert ".budget-tracker" not in str(s.banks_dir)

    def test_default_dir_uses_budget_tracker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default data paths resolve under ~/budget-tracker."""
        monkeypatch.delenv("BUDGET_TRACKER_TRANSACTIONS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORIES_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE", raising=False)
        monkeypatch.delenv("BUDGET_TRACKER_BANKS_DIR", raising=False)
        s = Settings()
        assert "budget-tracker" in str(s.transactions_file)
        assert "budget-tracker" in str(s.categories_file)
        assert "budget-tracker" in str(s.category_mappings_file)
        assert "budget-tracker" in str(s.banks_dir)


class TestMigrateDataDir:
    def test_migrate_data_dir_moves_old_to_new(self, tmp_path: Path) -> None:
        """Moves ~/.budget-tracker to ~/budget-tracker when old exists and new doesn't."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()
        (old / "transactions.json").write_text("[]")

        with patch("budget_tracker.config.settings.Path.home", return_value=tmp_path):
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

        with patch("budget_tracker.config.settings.Path.home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert old.exists()
        assert new.exists()
        assert not (new / "transactions.json").exists()

    def test_no_migration_when_old_does_not_exist(self, tmp_path: Path) -> None:
        """Does not raise when old dir is absent (fresh install)."""
        new = tmp_path / "budget-tracker"

        with patch("budget_tracker.config.settings.Path.home", return_value=tmp_path):
            _maybe_migrate_data_dir()

        assert not new.exists()

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        """Calling _maybe_migrate_data_dir twice is safe."""
        old = tmp_path / ".budget-tracker"
        new = tmp_path / "budget-tracker"
        old.mkdir()

        with patch("budget_tracker.config.settings.Path.home", return_value=tmp_path):
            _maybe_migrate_data_dir()
            _maybe_migrate_data_dir()  # second call: old gone, new exists — no error

        assert new.exists()
        assert not old.exists()
```

### README.md — MODIFY

New `## Cross-device sync` section inserted after `## How It Works`.

```markdown
## Cross-device sync

Your budget data lives in `~/budget-tracker/` by default. You can sync this folder with any cloud service to access your data across multiple devices.

> **Note:** Only use the app on one machine at a time to avoid data conflicts.

### Option 1: iCloud Drive

iCloud Drive syncs `~/budget-tracker/` automatically — no configuration required.

**Setup on Machine A:**
1. Open **System Preferences → Apple ID → iCloud → iCloud Drive Options** and ensure iCloud Drive is enabled.
2. Move your data folder into iCloud Drive:
   ```bash
   mv ~/budget-tracker ~/Library/Mobile\ Documents/com~apple~CloudDocs/budget-tracker
   ```
3. Add these lines to your shell profile (`~/.zshrc` or `~/.bash_profile`):
   ```bash
   export BUDGET_TRACKER_TRANSACTIONS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/transactions.json"
   export BUDGET_TRACKER_CATEGORIES_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/categories.yaml"
   export BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/category_mappings.yaml"
   export BUDGET_TRACKER_BANKS_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/banks"
   ```
4. Reload your shell: `source ~/.zshrc`

**Setup on Machine B:**
Add the same four env vars to your shell profile. On first run, the app will read data directly from your iCloud Drive folder.

> **Optimise Mac Storage:** If you have "Optimise Mac Storage" enabled in iCloud settings and the app shows an error about a file not being available, open Finder, navigate to your `budget-tracker` folder in iCloud Drive, and wait for the files to download (click the cloud icon). Then re-run the app.

---

### Option 2: Google Drive (Mirror mode)

Google Drive’s **Mirror mode** keeps a full local copy of your files, so the app always reads from disk.

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

On Machine B, set the same env vars using that machine’s local GDrive mirror path.

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

## Slices

### Slice 1: Settings default paths

**Files**: `src/budget_tracker/config/settings.py`

#### Automated Verification:
- [ ] Type checking passes: `ty check`
- [ ] `grep -n '\.budget-tracker' src/budget_tracker/config/settings.py | grep -v _maybe_migrate` returns 0 results

#### Manual Verification:
- [ ] `uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints a path ending in `budget-tracker/transactions.json` (no leading dot)
- [ ] Env-var override still works: `BUDGET_TRACKER_TRANSACTIONS_FILE=/tmp/x.json uv run python -c "from budget_tracker.config.settings import Settings; s = Settings(); print(s.transactions_file)"` prints `/tmp/x.json`

### Slice 2: Silent migration fn

**Files**: `src/budget_tracker/config/settings.py`

#### Automated Verification:
- [ ] Type checking passes: `ty check`
- [ ] `uv run pytest tests/unit/ -x -k "migration or migrate"` — skip if no matching tests yet (migration test added in Slice 4)

#### Manual Verification:
- [ ] Create `~/.budget-tracker/` with a dummy file; run app; verify `~/budget-tracker/` exists with the dummy file and `~/.budget-tracker/` is gone
- [ ] Run a second time with `~/budget-tracker/` already present; verify no error and no double-move
- [ ] Create both `~/.budget-tracker/` and `~/budget-tracker/`; verify migration does NOT fire (new already exists — guard holds)
- [ ] With no `~/.budget-tracker/` present; verify app starts normally (no error)

### Slice 3: OSError resilience in load() methods

**Files**: `src/budget_tracker/services/transaction_store.py`, `src/budget_tracker/services/category_cache.py`

#### Automated Verification:
- [ ] Type checking passes: `ty check`
- [ ] Tests pass: `uv run pytest tests/unit/test_transaction_store.py tests/unit/test_category_cache.py -x`

#### Manual Verification:
- [ ] Simulate iCloud eviction: create a file at the transactions path, then replace it with a non-readable file (`chmod 000`); verify `RuntimeError` is raised with the iCloud message
- [ ] Verify existing missing-file behaviour unchanged: if file does not exist, `load()` returns silently (no `RuntimeError`)
- [ ] Verify existing malformed-data behaviour unchanged: if file exists but contains valid JSON/YAML of the wrong type (e.g. a dict instead of a list for transactions), `load()` returns silently

### Slice 4: Test fixtures + migration tests

**Files**: `tests/unit/test_settings.py` (NEW), `tests/unit/test_budget_service.py` (no changes), `tests/unit/test_category_cache.py` (no changes)

#### Automated Verification:
- [ ] Type checking passes: `ty check`
- [ ] Tests pass: `uv run pytest tests/unit/ -x` (requires Slices 1–3 applied first)
- [ ] `grep -r '\.budget-tracker' tests/ | grep -v test_settings` returns 0 results

#### Manual Verification:
- [ ] New migration tests cover all 4 cases: move fires when old exists + new absent; no-op when new exists; no-op when old absent; idempotent on second call

### Slice 5: README cross-device sync section

**Files**: `README.md`

#### Automated Verification:
- [ ] Full test suite passes: `uv run pytest -x`

#### Manual Verification:
- [ ] `## Cross-device sync` section appears in README after `## How It Works`
- [ ] iCloud section documents the `~/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/` path correctly
- [ ] GDrive section covers both sub-patterns (direct relocation + My Computer in-place) with the modern `~/Library/CloudStorage/GoogleDrive-*/My Drive/` path
- [ ] Environment variables table shows `~/budget-tracker/` defaults (no leading dot)
- [ ] "Optimise Mac Storage" eviction is documented with recovery steps (not presented as a blocker)

## Desired End State

**Existing user on Machine A (has `~/.budget-tracker/`):**
```
# First run after update — migration fires silently inside get_settings()
$ budget-tracker
# ~/.budget-tracker/ → ~/budget-tracker/ (moved, not copied)
# App loads normally; ~/budget-tracker/transactions.json contains all prior data
```

**New user on Machine A:**
```
# First run — no migration needed; ~/budget-tracker/ created fresh
$ budget-tracker
# ~/budget-tracker/banks/ auto-created by ensure_banks_dir()
# ~/budget-tracker/categories.yaml seeded from config/categories.yaml
```

**iCloud sync setup (Machine A → Machine B):**
```
# Machine A: open System Preferences → iCloud Drive → iCloud Drive Options
# Check "Desktop & Documents Folders" OR use GDrive "My Computer" → Add ~/budget-tracker
#
# Machine B:
export BUDGET_TRACKER_TRANSACTIONS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/transactions.json"
export BUDGET_TRACKER_CATEGORIES_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/categories.yaml"
export BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/category_mappings.yaml"
export BUDGET_TRACKER_BANKS_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/banks"
```

**iCloud eviction (graceful error):**
```
# User has "Optimise Mac Storage" on; file evicted to cloud-only
$ budget-tracker
# App starts; on service init:
# RuntimeError: "Cannot read ~/budget-tracker/transactions.json — the file may have been
#   evicted by iCloud. Open Finder and wait for it to download, then try again."
# TUI shows notification; does not crash
```

## File Map

```
src/budget_tracker/config/settings.py          # MODIFY — rename defaults + migration fn
src/budget_tracker/services/transaction_store.py  # MODIFY — OSError resilience in load()
src/budget_tracker/services/category_cache.py     # MODIFY — OSError resilience in load()
tests/unit/test_settings.py                     # NEW — Settings defaults + migration tests
tests/unit/test_budget_service.py               # no-op — helpers already isolated (no dot-path refs)
tests/unit/test_category_cache.py               # no-op — helpers already isolated (no dot-path refs)
README.md                                        # MODIFY — cross-device sync section
```

## Ordering Constraints

- Slice 1 (settings defaults) must precede Slice 2 (migration fn) — both touch `settings.py` and the slice ordering avoids merge conflicts
- Slice 1 must precede Slice 3 (load resilience) — resilience tests use updated path names
- Slice 4 (test fixtures) must follow Slices 1–3 — fixtures test all three changes
- Slice 5 (README) is independent — can be written in any order

Note: `_maybe_migrate_data_dir()` uses hardcoded `Path.home() / ".budget-tracker"` paths (not Settings fields), so it has no runtime dependency on Slice 1's field changes. The ordering is for file-edit sequencing only.

## Verification Notes

- `grep -n '\.budget-tracker' src/budget_tracker/config/settings.py | grep -v _maybe_migrate` must return 0 results after Slice 1 (no dot-prefixed defaults in Settings class fields)
- `grep -r '\.budget-tracker' tests/ | grep -v test_settings` must return 0 results after Slice 4 (no non-migration test references old dot-prefixed path)
- Migration is idempotent: running `get_settings()` twice must not error if `~/budget-tracker` already exists
- `shutil.move` on a non-existent source must not raise (guard: `old.exists()`)
- New `~/budget-tracker` default must be created by `ensure_banks_dir()` if it doesn't exist
- `TransactionStore.load()` must not raise on a missing file (existing behaviour preserved)
- `TransactionStore.load()` must raise `RuntimeError` with iCloud message on `OSError`
- `CategoryCache.load()` must raise `RuntimeError` with iCloud message on `OSError`
- All existing tests pass after fixture updates

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

## Pattern References

- `settings.py:41-43` — seed-on-first-run guard structure (`if not exists → mkdir → copy2`); migration guard follows same shape
- `settings.py:56-58` — `get_settings()` as one-time init hook via `@cache`
- `transaction_store.py:30-31` — existing missing-file guard (`if not self._file_path.exists(): return`)
- `category_cache.py:21-23` — same pattern in CategoryCache
- `budget_service.py:37` — `ensure_banks_dir()` as the model for startup side effects in `__init__`

## Developer Context

**Step 4 — directional confirm:**
- Q: "Migration primitive: follow shutil.copy2 pattern (settings.py:41-43) or use shutil.move for whole directory rename?"
- A: "Moving off it — use shutil.move" → fixed decision

**Step 4 — scope decisions:**
- Q: "Is the code ready for cloud sync?" → confirmed env-var mechanism works today; iCloud caveats are the gap
- Q: "How to handle iCloud caveats?" → "change the code so we remove caveats"
- Q: "How to handle existing users?" → "silent migration"
- Q: "Migrate entire `~/.budget-tracker` dir or only known files?" → "yes sounds right" (entire dir via shutil.move)

## Design History

- Slice 1: Settings default paths — approved as generated
- Slice 2: Silent migration fn — approved as generated
- Slice 3: OSError resilience in load() — approved as generated
- Slice 4: Test fixture updates + migration test — approved as generated
- Slice 5: README cross-device sync section — approved as generated

## References

- `.rpiv/artifacts/solutions/2026-06-17_12-11-11_cloud-storage-sync.md` — parent solutions artifact
- `src/budget_tracker/config/settings.py:15-29` — env-var override infrastructure and data path defaults
- `src/budget_tracker/services/transaction_store.py:30-31` — missing-file guard pattern
- `src/budget_tracker/services/category_cache.py:21-23` — missing-file guard pattern
- `src/budget_tracker/services/budget_service.py:37-46` — startup init sequence
- Precedent: commit `0dfad18` — categories_file default path moved to ~/.budget-tracker/ (same blast radius)
- Precedent: commit `b64b586` — bank mappings storage migrated (settings field rename → test fixture updates required)
