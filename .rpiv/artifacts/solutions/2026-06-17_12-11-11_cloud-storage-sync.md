---
date: 2026-06-17T12:11:11+0200
author: unknown
commit: 486a1a7
branch: main
repository: budget-tracker
topic: "Cloud storage integration to preserve data across devices"
confidence: high
complexity: low
status: ready
verdict: pass
tags: [solutions, settings, transaction-store, category-cache]
last_updated: 2026-06-17T12:11:11+0200
last_updated_by: unknown
---

# Solution Analysis: Cloud Storage Integration

**Date**: 2026-06-17T12:11:11+0200
**Author**: unknown
**Commit**: 486a1a7
**Branch**: main
**Repository**: budget-tracker

## Research Question

Cloud storage integration so that the data is preserved across devices. The developer mentioned Dropbox/Google Drive-style sync as an example direction.

## Summary

**Problem**: Budget tracker data (`transactions.json`, `category_mappings.yaml`, `categories.yaml`, bank configs) lives at `~/.budget-tracker/` on a single machine and is not available on other devices.

**Recommended**: Cloud Folder Sync (Dropbox / Google Drive Mirror) — already works today via existing env-var overrides; zero code changes required.

**Effort**: Low (0 days of code; ~15 minutes of user setup)

**Confidence**: High

---

## Problem Statement

**Requirements:**
- Transaction data and category mappings persist and are accessible from multiple devices
- No data loss or corruption when switching between machines
- The solution must work with the existing TUI (Textual) and local-first architecture

**Constraints:**
- Hard: Must not introduce network I/O into the Textual event-loop main thread (would freeze the TUI)
- Hard: `transactions.json` is the authoritative data store; deduplication is by SHA256 `transaction_id` — concurrent writes from two machines must not produce invalid JSON
- Soft: Minimal new dependencies preferred
- Soft: Solution should work for a single user with 1-3 machines; not a multi-user scenario

**Success criteria:**
- User can run the budget tracker on Machine A, sync data to a cloud folder, then open Machine B and see the same transactions and category mappings
- No code changes required to the application itself (or minimal, if a richer sync option is chosen)
- The app continues to work fully offline

---

## Current State

**Existing implementation:**
All four persistent data paths are first-class `Settings` fields defined at `src/budget_tracker/config/settings.py:21-29`, each defaulting to `~/.budget-tracker/`:

| Settings field | Default path | Env var override |
|---|---|---|
| `categories_file` | `~/.budget-tracker/categories.yaml` | `BUDGET_TRACKER_CATEGORIES_FILE` |
| `banks_dir` | `~/.budget-tracker/banks/` | `BUDGET_TRACKER_BANKS_DIR` |
| `category_mappings_file` | `~/.budget-tracker/category_mappings.yaml` | `BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE` |
| `transactions_file` | `~/.budget-tracker/transactions.json` | `BUDGET_TRACKER_TRANSACTIONS_FILE` |

`Settings` inherits `pydantic_settings.BaseSettings` with `env_prefix="BUDGET_TRACKER_"` (`settings.py:15`). **All four paths are already overridable today via environment variables** — no code is required.

**Relevant patterns:**
- `pydantic_settings.BaseSettings` env-var override: `settings.py:12-15` — used in all settings injection
- `TransactionStore` atomic write: `transaction_store.py:51-54` — tmp file + `Path.replace()` (atomic rename)
- `@work(thread=True)` for blocking I/O: `categorization.py:278`, `export.py:59` — established pattern for isolating network/disk I/O from Textual event loop
- `httpx` synchronous remote call: `exchange_rate_provider.py:50` — existing precedent for remote I/O

**Integration points:**
- `src/budget_tracker/config/settings.py:21-29` — all data paths defined here
- `src/budget_tracker/services/budget_service.py:43-45` — TransactionStore and CategoryCache constructed from settings
- `src/budget_tracker/services/transaction_store.py:25,43` — `load()` and `save()` are the only I/O methods
- `src/budget_tracker/services/category_cache.py:21,51` — `load()` and `save()` for category mappings

---

## Solution Options

### Option 1: Cloud Folder Sync (Dropbox / Google Drive Mirror)

**How it works:**
The user moves `~/.budget-tracker/` into a Dropbox or Google Drive (Mirror mode) folder — or keeps data in place and sets four `BUDGET_TRACKER_*` environment variables pointing to cloud paths. The app already supports all four paths as named `Settings` fields overridable via env vars. The sync daemon (Dropbox / GDrive for Desktop) handles all replication transparently; the app has no awareness of the network.

**Two sub-patterns:**
1. **Direct relocation** (preferred): `cp -r ~/.budget-tracker ~/Dropbox/budget-tracker` and set env vars. On second machine, clone Dropbox folder, set same env vars.
2. **GDrive "My Computer" in-place sync**: Open GDrive for Desktop → Preferences → "My Computer" → Add folder → select `~/.budget-tracker`. Zero app config change. Only works in Mirror mode.

**Pros:**
- **Zero code changes** — `BUDGET_TRACKER_*` env vars already work; `Settings.ensure_banks_dir()` creates the cloud path on first run (`settings.py:34-37`); `load_categories()` seeds `categories.yaml` into the new path (`settings.py:40-44`); `TransactionStore.save()` creates its parent dirs (`transaction_store.py:50`)
- **Offline-first by design** — the app reads/writes local files; sync is transparent to the application
- **No new dependencies, no new auth** — user likely already has Dropbox or Google Drive
- **Zero test changes** — all 5 test files use `tmp_path` injection; none touch `~/.budget-tracker` directly
- **Atomic write compatible** — the `.tmp`→`Path.replace()` pattern (`transaction_store.py:51-54`) keeps the final JSON file always coherent; the `.tmp` sync event is cosmetic (sync daemon uploads `.tmp` file briefly, then sees the rename — no corruption)

**Cons:**
- **Requires user-owned Dropbox/GDrive** — not usable without an existing cloud sync account
- **iCloud Drive: dot-file exclusion** — iCloud's `bird` daemon skips `~/.budget-tracker/` (leading dot). User must rename the folder (remove dot) and set env vars. Also risk of "Optimise Mac Storage" evicting infrequently-accessed files to cloud-only, causing `FileNotFoundError` on offline runs. **iCloud is not recommended; Dropbox or GDrive Mirror is.**
- **Dropbox 2019 symlink change** — the symlink-bridge sub-pattern (symlink at `~/.budget-tracker` → inside Dropbox) was broken by Dropbox in 2019 for symlinks pointing outside the Dropbox root. Direct relocation is unaffected.
- **Concurrent multi-machine editing** — if the app is open simultaneously on two machines and both write `transactions.json`, Dropbox creates a "conflicted copy" (renamed file). The app opens the winning copy correctly; the conflict copy accumulates. Single-writer-at-a-time usage (the expected case for a personal budget tracker) never hits this.
- **GDrive: Mirror mode required** — Stream mode (the default on some installs) keeps files cloud-only unless the app is running; Mirror mode maintains a local copy always. User must verify/switch mode.

**Complexity:** Low (~0 days code; ~15 min user setup)
- Files to create: 0
- Files to modify: 0 (README documentation only)
- Risk level: Low

---

### Option 2: Supabase (Postgres + Storage)

**How it works:**
Replace `TransactionStore`'s JSON backend with a hosted Postgres database via `supabase-py`. The `StandardTransaction` Pydantic model maps cleanly to a SQL schema (all types are lossless: `Decimal`→`NUMERIC`, `date`→`DATE`, `str`→`TEXT`). `TransactionStore.load()` becomes `SELECT *` → hydrate in-memory dict; `save()` becomes batch `UPSERT` keyed by `transaction_id`. Category mappings can remain local or also migrate to a Supabase table.

```python
# Startup
response = supabase.table("transactions").select("*").execute()
# Save (dedup by transaction_id as PK)
supabase.table("transactions").upsert([t.model_dump() for t in batch]).execute()
```

**Pros:**
- `httpx` already a dependency; sync Supabase client fits naturally
- Single seam at `budget_service.py:43` — only one constructor change needed
- Clean `StandardTransaction`→SQL mapping; `NUMERIC` is more faithful to `Decimal` than JSON (eliminates the `Decimal(str(...))` workaround at `transaction_store.py:36-39`)
- `supabase-py` v2.31.0 (Jun 2026), actively maintained (~1.6 releases/month)
- Free tier covers budget-tracker scale (500 MB DB, 1 GB storage)
- Enables future querying/analytics at the DB layer

**Cons:**
- `_recompute` in `stats.py` fires on every filter-widget change (`stats.py:256`) — if it issues a Supabase `SELECT`, network call per keypress; requires debounce or in-memory cache layer (keep current query-in-memory pattern)
- `export.py:91` `save_transactions()` call is on the main thread (inside `call_from_thread` callback) — Supabase I/O here would block the TUI event loop; requires moving to its own `@work(thread=True)` worker
- Free tier: projects paused after 1 week inactivity — a personal budget tracker used infrequently **will hit this**; Pro plan is $25/month to avoid
- New cloud account + project setup (~20-30 min); RLS policy setup required (5-6 SQL statements)
- `test_transaction_store.py` (~170 lines, 5 classes) requires Protocol extraction or full restructuring; `pytest-mock` is present but new mock patterns needed (~100-150 lines)
- `supabase-py` v3.0 alpha exists (Apr 2026); watch for breaking changes in 2026H2
- Legacy API keys being deprecated by end-2026 (migrate to `sb_publishable_xxx` style)

**Complexity:** Medium (~2-3 days)
- Files to create: 1 (`supabase_store.py` adapter, ~80 lines) + schema DDL
- Files to modify: 3 (`settings.py`, `budget_service.py:43`, `test_transaction_store.py`)
- Risk level: Medium (main-thread I/O restructuring required; free-tier inactivity pausing)

---

### Option 3: S3-Compatible Backend (Cloudflare R2 / AWS S3 / MinIO)

**How it works:**
Store `transactions.json` (and optionally config files) in an S3-compatible object store. On startup, `boto3.download_file()` fetches the remote copy to `self._file_path` before `TransactionStore.load()` reads it; after every `TransactionStore.save()`, `boto3.upload_file()` pushes the updated file. The existing local file is the working copy; S3 is the remote backup/sync layer.

```python
# Startup (before load)
s3.download_file(bucket, 'transactions.json', str(self._file_path))
# After save
s3.upload_file(str(self._file_path), bucket, 'transactions.json')
```

**Pros:**
- Same boto3 code for all backends — only `endpoint_url` changes (AWS, R2, MinIO)
- `httpx` already present; established `@work(thread=True)` pattern for blocking I/O
- Atomic write (`transaction_store.py:51-54`) maps cleanly — upload fires after `Path.replace()`, always uploads a coherent file
- `boto3` is Production/Stable (v1.43.31 daily releases, Amazon-maintained, GA since 2015)
- Cloudflare R2: free egress, permanent free tier (10 GB + 1M PUT + 10M GET/month), effectively $0.00 for a solo user
- DI approach (optional S3 client in `TransactionStore.__init__`) preserves all 6 existing `test_transaction_store.py` tests unchanged

**Cons:**
- Both `load()` and `save()` are currently on the main thread — startup download blocks event loop; `export.py:91` save call too; both require `@work(thread=True)` restructuring
- `boto3` is a new heavy dependency (~13 MB with `botocore`); not justified when cloud folder sync achieves the same goal for free
- 4-5 external setup steps (R2 account, bucket, API token, 3 env vars); IAM concepts for AWS are particularly intimidating for non-developers
- New dev dependency (`moto` or `respx`) needed for S3 test mocking
- MinIO (free, self-hosted) is not a cross-device sync solution by itself — requires a publicly accessible server

**Complexity:** Medium (~2 days)
- Files to create: 1 (`s3_sync.py` wrapper, ~50 lines)
- Files to modify: 3 (`settings.py`, `budget_service.py` or `transaction_store.py`, `export.py`)
- Risk level: Medium (thread restructuring required; new heavy dependency)

---

### Option 4: Git Repo Sync (GitHub private repo / Gist)

> **Note: This option fails the fit filter — see Recommendation.**

**How it works:**
Store all data files in a private GitHub repo. `git pull --rebase` on startup, `git add -A && git commit && git push` after every save. SSH key or PAT required.

**Pros:**
- Well-established pattern (used by `pass`, `chezmoi`, `yadm`, Obsidian-git)
- Full version history of all budget changes
- Low external cost (GitHub free private repos)

**Cons / Blockers:**
- **Merge conflict blocker**: `transactions.json` is a monolithic JSON array; git performs line-level text merge. Two devices adding different transactions before a push/pull cycle produces a merge conflict at the closing `]` — syntactically invalid JSON that requires manual resolution. This is structural, not fixable without sharding data into per-period files (a significant schema change).
- `save_cache` (`categorization.py:163`) fires on every category assignment — naïve push-on-save would trigger `git push` dozens of times per import session
- Zero subprocess precedent in codebase; no git idioms anywhere; first non-local field in `Settings`
- SSH/PAT setup is real barrier for non-developer users
- Startup `git pull` in `BudgetService.__init__` would break all existing `BudgetService` unit tests unless a `is_git_repo()` guard is added

**Complexity:** Medium (~2-3 days) — but blocked on structural JSON merge conflict issue

---

## Comparison

| Criteria | Option 1: Cloud Folder Sync | Option 2: Supabase | Option 3: S3 Backend | Option 4: Git Sync |
|---|---|---|---|---|
| Code changes | None | ~80-100 lines | ~50 lines | ~100 lines |
| New dependencies | None | `supabase` | `boto3` | `GitPython` or subprocess |
| External setup | ~15 min | ~20-30 min | ~20-30 min | ~5-15 min |
| Offline-first | ✅ Always | ⚠️ Needs network on startup | ⚠️ Needs network on startup | ⚠️ Graceful degradation needed |
| Conflict handling | Dropbox "conflicted copy" (benign for single-writer) | Postgres upsert (clean) | Last-write-wins (benign for single-writer) | ❌ Invalid JSON on concurrent edits |
| Fit filter | ✅ Passes | ✅ Passes | ✅ Passes | ❌ Fails |
| Complexity | L | M | M | M (blocked) |
| Codebase fit | H | M | M | L |
| Risk | L | M | M | H |

---

## Recommendation

**Selected:** Option 1 — Cloud Folder Sync (Dropbox / Google Drive Mirror)

**Rationale:**

- **Already works today** — `BUDGET_TRACKER_TRANSACTIONS_FILE`, `BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE`, `BUDGET_TRACKER_CATEGORIES_FILE`, and `BUDGET_TRACKER_BANKS_DIR` are live env-var overrides right now (`settings.py:15` + `settings.py:21-29`). No code changes needed.
- **Zero test changes** — all 5 test files use `tmp_path` injection; none reference `~/.budget-tracker`; the test suite passes identically regardless of where data lives.
- **Zero risk of TUI freezes** — the app never makes a network call; sync is the cloud daemon's responsibility. Options 2 and 3 both require `@work(thread=True)` restructuring to avoid blocking the Textual event loop.
- **Offline-first without extra design** — if the sync daemon isn't running, the app reads/writes local files exactly as today.
- **Single-user model matches the app's design** — the app has no multi-user auth, no conflict-resolution UI, no connectivity error screens. Cloud folder sync requires none of that.

**Why not Option 2 (Supabase):** Technically the best option if the goal extends to querying/analytics at the DB layer, or if the developer wants to eventually build a web companion. But for "preserve data across devices" alone, it introduces significant accidental complexity: free-tier inactivity pausing, main-thread I/O restructuring, Protocol extraction in tests, and cloud account management — when the same sync goal is achievable at zero cost.

**Why not Option 3 (S3):** Technically sound and future-proof (boto3 is rock-solid), but same objection as Supabase: the code and external setup complexity is unjustified when Option 1 achieves identical sync semantics.

**Why not Option 4 (Git):** Fails the fit filter. The monolithic `transactions.json` + git line-level merge produces unresolvable conflicts on concurrent device edits. Would require sharding data into per-period files to be viable.

**Trade-offs:**
- Accepting dependency on user-owned Dropbox/GDrive for zero app code
- Accepting Dropbox "conflicted copy" artifacts under simultaneous multi-machine use (unlikely for a personal budget tool)
- Accepting that iCloud Drive requires extra steps (dot-folder rename + eviction risk) and is not the recommended provider

**Conditions that would change the recommendation:**
- If the developer wants cross-device *real-time* sync or a web companion → Supabase becomes the right choice
- If the target audience has no cloud sync service → S3 (R2) is the next cleanest option with no inactivity-pause problem
- If the data files are sharded into per-period files → Git sync becomes viable and gains version-history benefits

**Implementation approach (Option 1):**

1. **Document the four env vars in README** — add a "Cross-device sync" section showing Dropbox and GDrive Mirror setup
2. **On first machine**: `cp -r ~/.budget-tracker ~/Dropbox/budget-tracker` then add to shell profile:
   ```bash
   export BUDGET_TRACKER_TRANSACTIONS_FILE="$HOME/Dropbox/budget-tracker/transactions.json"
   export BUDGET_TRACKER_CATEGORY_MAPPINGS_FILE="$HOME/Dropbox/budget-tracker/category_mappings.yaml"
   export BUDGET_TRACKER_CATEGORIES_FILE="$HOME/Dropbox/budget-tracker/categories.yaml"
   export BUDGET_TRACKER_BANKS_DIR="$HOME/Dropbox/budget-tracker/banks"
   ```
3. **Wait for initial sync** (Dropbox icon stops animating)
4. **On second machine**: clone Dropbox folder, set the same 4 env vars

**Alternatively for GDrive "My Computer" in-place sync (zero config change):**
1. Open GDrive for Desktop → Preferences → My Computer → Add Folder → select `~/.budget-tracker`
2. Verify Mirror mode is active (not Stream)
3. On second machine: set `BUDGET_TRACKER_*` env vars to the local GDrive "Computers > Machine Name" path

**Integration points (documentation only):**
- `src/budget_tracker/config/settings.py:15` — `env_prefix="BUDGET_TRACKER_"` is the hook
- `src/budget_tracker/config/settings.py:21-29` — the four path fields and their defaults
- `src/budget_tracker/services/transaction_store.py:50` — `self._file_path.parent.mkdir(parents=True, exist_ok=True)` auto-creates cloud directory structure

**Patterns to follow:**
- Settings field override: `settings.py:15` (existing `env_prefix` pattern)

**Risks:**
- iCloud Drive dot-file exclusion: Mitigation — document that iCloud requires renaming `budget-tracker` (no dot), with the path `~/Library/Mobile Documents/com~apple~CloudDocs/budget-tracker/`; recommend Dropbox or GDrive Mirror instead
- Dropbox "conflicted copy" on simultaneous two-machine write: Mitigation — document that users should close the app on one machine before opening on another; the conflict copy is always safely named and never overwrites the primary
- GDrive Stream mode (not Mirror): Mitigation — README must specify "Mirror mode required"; include screenshot or Settings path

---

## Scope Boundaries

- **In scope**: Documentation of the existing env-var mechanism; README "Cross-device sync" section; optional shell profile snippet
- **Out of scope**: Code changes to the application (none needed for Option 1)
- **Out of scope**: Multi-user sync, conflict-resolution UI, real-time sync, web companion
- **Out of scope**: Windows support (Dropbox and GDrive for Windows exist but paths differ; the env-var mechanism works on all platforms)

---

## Testing Strategy

**Unit tests:** No changes required — all storage tests already use `tmp_path` injection.

**Integration tests:** None required — sync is handled by the OS daemon, not the app.

**Manual verification:**
- [ ] Set `BUDGET_TRACKER_TRANSACTIONS_FILE` to a Dropbox path; run app, import a CSV, verify `transactions.json` appears in Dropbox
- [ ] On second machine with same env var set, run app and verify imported transactions appear
- [ ] Verify the app starts correctly with no Dropbox/network available (offline mode: reads local file as usual)
- [ ] Verify `~/.budget-tracker/` is unaffected when env vars point elsewhere (no accidental double-write)
- [ ] (iCloud only) Verify dot-folder exclusion behavior by checking iCloud.com web UI for presence of `budget-tracker` folder

---

## Open Questions

**Resolved during research:**
- Are data paths already env-var overridable? — **Yes, fully**; `pydantic_settings.BaseSettings` with `env_prefix="BUDGET_TRACKER_"` at `settings.py:15`; all 4 data paths are named fields
- Is the atomic write compatible with cloud sync? — **Yes**; `.tmp`→`Path.replace()` keeps the final file coherent; `.tmp` upload is cosmetic
- Does any code hardcode `~/.budget-tracker` outside settings? — **No**; the grep confirms all 4 occurrences of `Path.home() / ".budget-tracker"` are exclusively in `settings.py:21-29`
- Does iCloud work for dot-prefixed directories? — **No**; `bird` daemon excludes dot-prefixed names; folder must be renamed and path updated

**Requires user input:**
- Which cloud provider does the user have? (Dropbox, GDrive, iCloud, or none) — Default assumption: Dropbox or GDrive; iCloud documented with caveats
- Is the README the right place for this documentation, or should a `--setup-sync` CLI flag be added? — Default: README only (no code needed)

**Blockers:** None — Option 1 is unblocked and implementable today.

---

## References

- `src/budget_tracker/config/settings.py:15-29` — env-var override infrastructure and data path defaults
- `src/budget_tracker/services/transaction_store.py:51-54` — atomic write pattern (compatible with cloud sync)
- `src/budget_tracker/services/budget_service.py:43-45` — TransactionStore and CategoryCache construction (single seam for Option 2/3 future work)
- `src/budget_tracker/currency/exchange_rate_provider.py:50` — existing httpx sync remote-call precedent
- https://help.dropbox.com/sync/symlinks — Dropbox symlink behavior (direct relocation preferred over symlink bridge)
- https://help.dropbox.com/organize/conflicted-copy — Dropbox conflict model (benign for single-writer)
- https://support.google.com/drive/answer/2375012 — GDrive Mirror vs Stream (Mirror required)
- https://supabase.com/docs/reference/python/introduction — Supabase Python client v2 reference
- https://developers.cloudflare.com/r2/examples/boto3/ — R2 + boto3 integration example
- https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html — boto3 S3 upload guide
