---
date: 2026-07-17T14:49:54+02:00
topic: "zero-touch csv import engine"
tags: [design, ingestion, parsing, categorization, cli]
status: draft
related_research: .rpi/research/2026-07-17-low-friction-local-only-ingestion-and-web-pipeline-completion.md
spec: .rpi/specs/zero-touch-csv-import.md
---

# Design: zero-touch csv import engine

## Summary

Turn ingestion from a per-file interactive TUI pipeline into a headless
engine: `budget-tracker import *.csv` fingerprints each file's bank, parses it
(all four banks: Danske Bank, mBank, Revolut, Wise), auto-confirms transfer
pairs, categorizes via user-authored rules, and saves with dedup — no
questions asked. Leftovers land as `Uncategorized` and are fixed by editing
rules and running `budget-tracker recategorize`. This is Track A of the
research; the web upload/review UI is Track B and reuses this engine.

## Context

The tool fell out of use because ingestion is high-touch and half the user's
banks can't even be parsed (research §1, §4). The user has since decided the
TUI is on its way out entirely — the surfaces going forward are **web + CLI**.
That reshapes Track A: instead of wiring fingerprinting into
`FileSelectionScreen`, Track A delivers the engine as service-layer code plus
a new headless CLI, and freezes the TUI (no new TUI work; deletion happens
when Track B ships).

Current state (evidence):

- Parsing: `CSVParser.parse_file` (`src/budget_tracker/parsers/csv_parser.py:51-68`)
  hard-codes encoding detection (UTF-8 → ISO-8859-1, `csv_parser.py:24-33`),
  sniffs the delimiter from the first 1024 bytes, and assumes row 0 is the
  header. `BankMapping` (`src/budget_tracker/models/bank_mapping.py:15-31`)
  has no encoding / delimiter / header-offset / row-filter fields. This is
  why mBank (cp1250 + preamble) and Revolut (REVERTED rows) can't be parsed.
- Bank selection is fully manual: `FileSelectionScreen.action_add_file`
  (`src/budget_tracker/tui/screens/file_selection.py:122-168`) requires a
  dropdown pick per file.
- Categorization: exact-match only — `CategoryCache.get`
  (`src/budget_tracker/services/category_cache.py:61-63`) is a dict lookup on
  the full description; the TUI wizard auto-applies only exact hits
  (`tui/screens/categorization.py:102-118`).
- Mappings live in `~/budget-tracker/banks/*.yaml` at runtime
  (`config/settings.py:23`, `services/budget_service.py:59-79`); the repo's
  `config/banks/danske_bank.yaml` is a reference copy that is **not** seeded
  (unlike categories, which seed via `config/settings.py:39-45`).
- Dedup already works: `TransactionStore.add_many`
  (`services/transaction_store.py:69-77`) skips existing `transaction_id`s
  (SHA256 over date|amount|source|description,
  `models/transaction.py:65-83`). Consequence: overlapping re-imports are
  safe, but a re-import can never *change* an already-saved row — hence the
  explicit `recategorize` command below.
- `StandardTransaction.category` is required and validated against
  `categories.yaml` (`models/transaction.py:24-39`), so "save without
  category" needs an explicit `Uncategorized` concept.
- The only entry point today is `budget-tracker = budget_tracker.tui:main`
  (`pyproject.toml:41-42`); there is no CLI.

## Inherited Decisions

From `.rpi/research/2026-07-17-low-friction-local-only-ingestion-and-web-pipeline-completion.md`:

> - **No aggregators — local-only ingestion** (user, 2026-07-17).
> - **Monthly manual download per bank is the accepted floor**; everything after
>   must be near-zero-touch (user, 2026-07-17).
> - **Deployment target is home network/server** — supersedes localhost-only
>   scope in the 2026-06-17 research (user, 2026-07-17).
> - Banks in scope: **Danske Bank, mBank, Revolut, Wise** (user, 2026-07-17).

## Decisions

- **TUI is frozen, not deleted here** (user, 2026-07-17): no new TUI
  features; the `tui/` package stays runnable as a fallback review surface
  and is deleted when Track B ships. Surfaces going forward: web + CLI.
- **Track A's user surface is a headless CLI** (`import`, `recategorize`),
  with orchestration in `BudgetService` so Track B's upload endpoint reuses
  it verbatim.
- **Categorization rules are YAML-authored** (user, 2026-07-17): a
  hand-editable ordered rules file; no rule-authoring UI in Track A. The
  exact-match cache stays as fast path; the wizard keeps writing cache
  entries as today.
- **Rules-missed rows are saved as `Uncategorized`** (user, 2026-07-17): a
  built-in always-valid category. The import summary lists their
  descriptions; `recategorize` re-applies rules to stored Uncategorized
  rows (required because store dedup makes re-import a no-op for existing
  rows).
- **Detected transfer pairs are auto-confirmed** (user, 2026-07-17): no
  confirmation step; accepted false-positive risk, undo/review is Track B.
- **Ambiguous or unknown fingerprints never guess**: zero or multiple
  matches → the file is skipped and reported; the rest of the batch
  proceeds. New/unknown banks are onboarded by hand-authoring a mapping
  YAML (or the frozen TUI flow, which still works).
- **`get_cached_category` gains rules awareness**: the service method the
  frozen TUI wizard already calls (`tui/screens/categorization.py:108`)
  delegates to cache-then-rules, so the TUI benefits with zero TUI edits.

## Constraints

- Transaction data never leaves the machine; no third-party service is
  involved in ingestion (inherited: no aggregators).
- No new runtime dependencies: CLI on `argparse`; parsing stays
  pandas/pydantic/PyYAML.
- All new `BankMapping` fields are optional with today's behavior as
  defaults — existing user mapping YAMLs keep working unchanged.
- No data migration: existing `transactions.json`, `category_mappings.yaml`,
  and user mapping files are read as-is.
- No TUI file is modified, and the TUI keeps working (frozen ≠ broken). One
  deliberate behavior improvement reaches it through the service layer: the
  wizard's auto-apply (`tui/screens/categorization.py:102-118`) starts
  matching rules, not just exact cache hits, because `get_cached_category`
  gains rules awareness (Component 3).
- Every saved transaction has a valid category (validation regime of
  `models/transaction.py:24-39` preserved; `Uncategorized` becomes valid by
  construction).

## Components

### 1. Parser & mapping format extensions

**Files:** `src/budget_tracker/models/bank_mapping.py`,
`src/budget_tracker/parsers/csv_parser.py`

Extend `BankMapping` with optional fields (all defaulting to current
behavior):

- `encoding: str | None = None` — explicit codec (e.g. `cp1250` for mBank).
  `None` keeps today's UTF-8 → ISO-8859-1 probe. This is the only reliable
  fix: cp1250 vs latin-1 cannot be distinguished by probing since both accept
  nearly every byte sequence.
- `delimiter: str | None = None` — explicit separator (e.g. `;`), bypassing
  the sniffer (which the mBank preamble confuses).
- `header_row: int = 0` — 0-based line index of the header; earlier lines
  (mBank metadata preamble) are skipped via `pd.read_csv(skiprows=...)`.
- `row_filters: list[RowFilter] = []` — new `RowFilter` model:
  `column: str`, `op: Literal["equals", "not_equals"]`, `value: str`.
  A row is kept only if all filters pass (e.g. Revolut:
  `State equals COMPLETED`, which also drops REVERTED holds).

`CSVParser.parse_file` gains an optional `mapping` parameter: when given, it
uses the mapping's encoding/delimiter/header offset and parses ragged trailing
metadata tolerantly (`on_bad_lines="skip"`); without a mapping it behaves
exactly as today (used by the frozen TUI's `detect_columns` path,
`budget_service.py:49-51`). `load_with_mapping` applies `row_filters` after
the dataframe loads, before field extraction.

Tested by extending `tests/unit/test_parser.py` against new per-bank fixture
CSVs in `tests/fixtures/` (following the existing `sample_<bank>.csv`
naming), which exercise encoding, preamble skip, and row filters.

*Alternative considered:* per-bank parser subclasses. Rejected — the
declarative YAML mapping pattern already exists, is user-editable, and four
config values + one filter list cover all four banks' quirks.

### 2. Bank fingerprinting

**Files:** `src/budget_tracker/services/bank_detector.py` (new),
`src/budget_tracker/models/bank_mapping.py` (fingerprint field),
`src/budget_tracker/services/budget_service.py` (`identify_bank`)

Add `fingerprint: list[list[str]] | None = None` to `BankMapping`: a list of
header-set variants; each variant is a list of column names that must all be
present in the file's header row. Variants cover Revolut's locale-dependent
headers (English first; other locales appended as encountered).

`BankDetector.identify(file_path, mappings) -> BankMapping | None`:

1. For each mapping with a fingerprint: decode the file with the mapping's
   declared encoding (or the default probe), read the line at the mapping's
   `header_row`, split on the mapping's delimiter (or sniff), strip
   BOM/whitespace from cells.
2. A mapping matches if any variant's names are all present in those cells
   (subset match — robust to extra columns).
3. Exactly one match → that mapping. Zero or several → `None` (never guess).

The four banks' headers are mutually distinctive (`Dato;Beløb…` vs
`#Data;#Opis operacji…` vs `Type,Product,Started Date…` vs
`TransferWise ID,…` — research §5), so collisions are theoretical until many
mappings exist; ambiguity handling still errs safe.

Exposed as `BudgetService.identify_bank(file_path)`. Mappings created via the
frozen TUI's `ColumnMappingScreen` won't have fingerprints (no TUI edits) —
those banks simply aren't auto-detected until the user adds a `fingerprint:`
block by hand. Acceptable: all four in-scope banks ship with fingerprints
(Component 4). Tested in new `tests/unit/test_bank_detector.py` (all four
fixtures identify; ambiguous and unknown headers return `None`) plus
`test_parser.py` coverage for the `fingerprint` mapping field.

### 3. Rule-based categorization

**Files:** `src/budget_tracker/services/category_rules.py` (new),
`src/budget_tracker/config/settings.py` (`category_rules_file` path),
`src/budget_tracker/services/budget_service.py` (`suggest_category`)

New `CategoryRules` service, following the `CategoryCache` shape (load
YAML → validate → in-memory list). Rules file
`~/budget-tracker/category_rules.yaml`:

```yaml
rules:
  - match: "netto"            # case-insensitive substring (default)
    category: Groceries
  - match: "^PKP\\s"          # regex when match_type: regex
    match_type: regex
    category: Transport
    subcategory: Train
```

Semantics: ordered, first match wins; matching is case-insensitive against
the transaction description. Rules whose category/subcategory fail validation
against `categories.yaml` are skipped **loudly** (warning naming the rule) —
unlike `CategoryCache.load`'s silent skip (`category_cache.py:48-59`),
because rules are hand-authored and typos must surface.

Resolution order in `BudgetService.suggest_category(description)`:
exact cache hit (`category_cache.py:61-63`) → first matching rule → `None`.
`get_cached_category` (`budget_service.py:137`) delegates to
`suggest_category`, upgrading the frozen TUI wizard for free.

No auto-derivation of rules from the cache (user decision) — the import
summary's uncategorized-descriptions list is the authoring feedback loop.

Tested in new `tests/unit/test_category_rules.py` (ordering, case
insensitivity, regex mode, loud invalid-rule handling, cache-before-rules
resolution).

### 4. Shipped bank configs + seeding

**Files:** `config/banks/mbank.yaml`, `config/banks/revolut.yaml`,
`config/banks/wise.yaml` (new), `config/banks/danske_bank.yaml` (add
fingerprint), `src/budget_tracker/config/settings.py` (seed logic),
`src/budget_tracker/services/budget_service.py` (seed call on init)

Ship complete mappings (columns, date format, decimal separator, currency
column where present, encoding/delimiter/header_row/row_filters, fingerprint)
for all four banks. mBank/Revolut/Wise values start from the research's
second-hand format tables (research §4) and **must be confirmed against one
real export each during implementation** — fixtures are built from those
(anonymized) files.

Seeding (mirrors the categories pattern, `settings.py:39-45`): on service
init, for each `config/banks/*.yaml` missing from `~/budget-tracker/banks/`,
copy it. For a user file that already exists (the user's live
`danske_bank.yaml`) and lacks a `fingerprint` while the shipped config has
one, backfill **only** the missing `fingerprint` field — never overwrite
user-tuned columns/blacklists. User file always wins otherwise.

### 5. Headless import & recategorize orchestration

**Files:** `src/budget_tracker/services/budget_service.py`
(`import_files`, `recategorize_uncategorized`),
`src/budget_tracker/models/import_result.py` (new),
`src/budget_tracker/models/transaction.py` (`UNCATEGORIZED` constant),
`config/categories.yaml` (add `Uncategorized`)

`BudgetService.import_files(paths) -> ImportResult` — the engine Track B's
upload endpoint will call:

1. Per file: `identify_bank`; unidentified → recorded in the result, file
   skipped, batch continues.
2. Parse identified files via `BudgetService.parse_file` →
   `CSVParser.load_with_mapping` (Component 1).
3. Pool all parsed transactions → `detect_transfers`
   (`budget_service.py:83-87`) → every detected pair auto-confirmed via
   `create_transfer_transaction` (`budget_service.py:114`), same as the TUI
   accept path.
4. Remaining rows → `suggest_category`; hit → `create_transaction` with the
   suggestion (converting currency exactly as the TUI does,
   `budget_service.py:91-112`); miss → category `Uncategorized`.
5. `save_transactions` (`budget_service.py:213`) → store dedups; duplicates
   = attempted − added.

`ImportResult` (pydantic): per-file entries (path, detected bank or
unidentified, parsed/skipped row counts), totals (transfers paired,
categorized via cache, via rules, uncategorized with the distinct
description list, duplicates skipped, newly saved).

`Uncategorized` handling: `UNCATEGORIZED = "Uncategorized"` constant in
`models/transaction.py`; `validate_category` accepts it unconditionally so
existing installs (whose `~/budget-tracker/categories.yaml` predates it and
is only seeded when absent) need no migration. Also added to
`config/categories.yaml` so fresh installs see it as a normal category.
Note: `config/categories.yaml:90` already has an "Uncategorized"
*subcategory* under "Other" — a distinct, pre-existing bucket. The new
top-level category does not touch it, and `recategorize_uncategorized` only
matches the top-level category; historical "Other/Uncategorized" rows are
left alone (renaming that legacy subcategory is out of scope).

`BudgetService.recategorize_uncategorized() -> int`: iterate stored
transactions with category `Uncategorized`, re-apply `suggest_category`,
mutate matches in place (model is mutable, `transaction.py:15`; category is
not part of `transaction_id`, so identity is stable), save the store, return
the changed count. This closes the loop: import → read summary → author
rules → `recategorize`.

### 6. CLI entry point

**Files:** `src/budget_tracker/cli.py` (new), `pyproject.toml` (entry point)

`budget-tracker` becomes an `argparse` dispatcher
(`pyproject.toml` script → `budget_tracker.cli:main`):

- `budget-tracker` (no args) / `budget-tracker tui` — launch the frozen TUI
  (unchanged default until Track B).
- `budget-tracker import <files...>` — run `import_files`, print the
  summary: per-file bank + counts, transfers paired, cache/rule hits,
  uncategorized descriptions (the rule-authoring worklist), duplicates
  skipped, saved count. Exit 0 if every file identified and parsed, 1
  otherwise. Strictly non-interactive.
- `budget-tracker recategorize` — run `recategorize_uncategorized`, print
  the changed count.

Import orchestration, recategorize, summary content, and exit codes are
tested in new `tests/unit/test_import_flow.py` (shared with Component 5).

## File Structure

New:

- `src/budget_tracker/services/bank_detector.py` — Component 2
- `src/budget_tracker/services/category_rules.py` — Component 3
- `src/budget_tracker/models/import_result.py` — Component 5
- `src/budget_tracker/cli.py` — Component 6
- `config/banks/mbank.yaml`, `config/banks/revolut.yaml`,
  `config/banks/wise.yaml` — Component 4
- `tests/unit/test_bank_detector.py` — Component 2
- `tests/unit/test_category_rules.py` — Component 3
- `tests/unit/test_import_flow.py` — Components 5–6 (import, recategorize,
  CLI summary/exit codes)
- `tests/fixtures/sample_mbank.csv`, `tests/fixtures/sample_revolut.csv`,
  `tests/fixtures/sample_wise.csv` — anonymized fixture CSVs, existing
  naming convention — Components 1, 4

Modified:

- `src/budget_tracker/models/bank_mapping.py` — Components 1 (parsing
  fields, `RowFilter`), 2 (`fingerprint`)
- `src/budget_tracker/parsers/csv_parser.py` — Component 1
- `src/budget_tracker/config/settings.py` — Components 3 (rules file path),
  4 (shipped-banks dir + seeding)
- `src/budget_tracker/services/budget_service.py` — Components 2
  (`identify_bank`), 3 (`suggest_category` + `get_cached_category`
  delegation), 4 (seed on init), 5 (`import_files`,
  `recategorize_uncategorized`)
- `src/budget_tracker/models/transaction.py` — Component 5 (`UNCATEGORIZED`)
- `config/banks/danske_bank.yaml` — Component 4 (fingerprint)
- `config/categories.yaml` — Component 5 (`Uncategorized` category)
- `pyproject.toml` — Component 6 (entry point)
- `tests/unit/test_parser.py` — extended for new mapping fields and
  filtered parsing — Components 1, 2

## Risks

- **Second-hand format specs.** mBank/Revolut/Wise details come from
  community/accounting docs (research §4). Mitigation: implementation starts
  by validating one real export per bank; mapping YAMLs are config, so
  corrections don't touch code.
- **Transfer auto-confirm false positives.** A coincidental same-day,
  same-amount, opposite-sign pair across banks is silently excluded from
  spending. User-accepted; Track B's review screen adds visibility/undo.
  The import summary lists paired transfers so misfires are at least visible.
- **Over-broad rules miscategorize silently.** First-match-wins ordering +
  the summary's per-category counts keep it inspectable; rules are
  hand-authored (no auto-derivation), which was chosen precisely to keep
  intent explicit.
- **Fingerprint collision as mappings accumulate.** Ambiguity → skip and
  report, never guess; worst case is a manually-specified import, not a
  wrong parse.
- **cwd-relative `config_dir`** (`settings.py:17-22`): seeding shipped
  configs only works when running from the repo directory. This matches the
  existing categories-seeding behavior — unchanged here, and moot once the
  home-server deployment (Track B) pins a working directory.
- **`Uncategorized` bucket in stats.** Until rules mature, dashboards show a
  lump. This is by design (data lands in one pass); the
  summary + `recategorize` loop shrinks it over time.

## Out of Scope

- Web upload endpoint, batch-review UI, and deployment/auth decisions
  (Track B — `.rpi` research §6–7).
- Deleting the `tui/` package (happens when Track B ships).
- Rule-authoring UI (Track B review screen may add it).
- Transfer review/undo and transfer-pattern learning.
- Automatic statement download / portal scraping (research §8).
- Tombstone dedup for deleted transactions (no deletion feature exists;
  research §2 caveat).
- Wise `TransferWise ID`-based identifier dedup (hash dedup suffices).
- Fingerprint capture in the TUI's `ColumnMappingScreen` (TUI frozen).

## References

- Research: `.rpi/research/2026-07-17-low-friction-local-only-ingestion-and-web-pipeline-completion.md`
- Spec: `.rpi/specs/zero-touch-csv-import.md`
- Firefly III rules engine and import-config prior art — cited in research §3, §5.
