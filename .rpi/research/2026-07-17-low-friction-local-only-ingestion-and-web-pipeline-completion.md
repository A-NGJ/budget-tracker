---
branch: main
date: 2026-07-17T14:35:04+02:00
git_commit: a3dd57d
repository: budget-tracker
researcher: Claude
status: active
tags:
    - research
    - ingestion
    - parsing
    - web
    - categorization
topic: low-friction local-only ingestion and web pipeline completion
---

# Research: low-friction local-only ingestion and web pipeline completion

## Research Question

The tool has fallen out of use: getting data in requires visiting each bank,
downloading a statement, and pushing it through a multi-step TUI pipeline by
hand. What would make the whole loop (data in → categorized → stats) low-effort
enough to actually use — **without** third-party bank-data aggregators — and
what should finishing the web migration look like now that the target is a
home-network server rather than localhost?

## Problem Statement

User-confirmed scope (interview, 2026-07-17):

- **Banks:** Danske Bank (DK), mBank (PL), Revolut, Wise. Only Danske Bank has
  a mapping configured today — the Polish/fintech accounts have never been set
  up, so the tool doesn't cover part of the user's money.
- **No aggregators.** Open-banking aggregator flow (GoCardless/Tink/SaltEdge)
  was explained and declined — data must stay local; no third party holds
  transaction history.
- **Acceptable friction bar:** a ~monthly visit to each bank portal to download
  a file is OK. Everything after that must be one drag-drop with no questions
  for known merchants.
- **Deployment:** home network / server (LAN or Tailscale), reachable from
  phone + laptop. This **supersedes** the localhost-only decision in
  `.rpi/research/2026-06-17-tui-to-local-web-app-migration.md`.

## Summary

The friction has two halves, and both are addressable locally:

1. **Ingestion** — the current pipeline demands per-file manual work (path
   entry, bank selection, transfer review, one-by-one categorization) and the
   parser can't even read two of the four banks' exports (mBank's cp1250
   encoding + metadata preamble; Revolut's REVERTED rows). Fixes: bank
   auto-detection by header fingerprint, four parser upgrades (encoding,
   header offset, row filters, delimiter override), and rule-based
   categorization replacing the exact-match cache.
2. **Interaction surface** — the interactive pipeline exists only in the TUI,
   which is unusable from a phone and requires files to live on the machine
   running it. On a home server, **web upload is not a nice-to-have; it is the
   only way files (downloaded on laptop/phone) reach the app.**

Critically, **the enabler already exists**: `TransactionStore` dedupes by
SHA256 `transaction_id`, so overlapping re-imports are safe — "download last
90 days once a month, drop everything in, let the store sort it out" works
with today's persistence layer.

Target loop after the change: ~monthly, download 4 files → drag onto the web
app from any device → app fingerprints each file, parses, dedupes,
auto-confirms transfers it's seen the shape of, auto-categorizes via rules →
one consolidated review screen for the leftovers → done. Estimated interaction:
minutes, mostly zero-question.

## Detailed Findings

### 1. Where the manual effort actually goes (codebase)

The TUI pipeline (`src/budget_tracker/tui/app.py`, `tui/state.py:18-42`):
Home → FileSelection → TransferReview → PeriodSelection → Categorization
(one-by-one wizard) → Export/Stats. Per file, the user must type a path and
pick the bank from a dropdown (`tui/screens/file_selection.py` — `bank_value`
selection, `__new__` branch opens `ColumnMappingScreen`). Nothing identifies a
bank from file content.

### 2. Duplicate protection already exists (enabler)

`src/budget_tracker/services/transaction_store.py:23-26` — class docstring:
"Deduplicates transactions by transaction_id (SHA256 hash)". In-memory dict
keyed by hash, JSON persistence, atomic write. Consequence: overlapping
date-range imports are already safe; no import-window bookkeeping needed.

Caveat noted from prior art: Firefly III deliberately checks *deleted*
transactions during dedup so purged bad rows don't resurrect on the next
overlapping import
([Firefly III duplicate-detection docs](https://docs.firefly-iii.org/references/data-importer/duplicate-detection/)).
The current store has no tombstone concept — if transaction deletion is ever
added, re-imports would resurrect deleted rows. Design consideration, not a
current bug.

### 3. Categorization cache is exact-match only (main wizard cost)

`src/budget_tracker/services/category_cache.py` — `get`/`set` on the **full
description string**. Descriptions containing dates, amounts, or reference
numbers never repeat exactly, so they hit the wizard every time, forever.

Prior art: Firefly III's rule engine (trigger "description contains X" →
action "set category Y", applied at import time) is the standard solution —
"even when there is the tiniest bit of information in your transactions, you
can use the rule engine to … make them more complete"
([rules how-to](https://docs.firefly-iii.org/how-to/firefly-iii/features/rules/)).
A substring/regex rule table (seedable from the existing exact-match cache
entries) would collapse most wizard interactions to zero.

### 4. Parser gaps vs. the four banks' real export formats

Current `CSVParser` (`src/budget_tracker/parsers/csv_parser.py`):
- `detect_encoding` tries **UTF-8 then ISO-8859-1 only**. ISO-8859-1 accepts
  every byte sequence, so it never fails — files in any other 8-bit encoding
  silently mis-decode.
- `detect_delimiter` sniffs the first 1024 bytes with `csv.Sniffer`.
- `BankMapping`/`ColumnMapping` (`src/budget_tracker/models/bank_mapping.py`)
  has: column names, date format, decimal separator, default currency,
  blacklist keywords (stripped from description text). **No** encoding
  override, no header-row offset, no delimiter override, no row-level filter.

Per-bank reality:

| Bank | Format | Breaks current parser? |
|---|---|---|
| **Danske Bank** | CSV, `Dato/Beløb/Tekst…`, `%d.%m.%Y`, comma decimal, DKK (working mapping: `config/banks/danske_bank.yaml`) | No — already works |
| **mBank (PL)** | CSV/TXT, **Windows-1250**, **semicolon**-separated, columns `#Data;#Data ksiegowania;#Opis operacji;#Tytul;#Nadawca/Odbiorca;#Numer konta;#Kwota;#Saldo po operacji`, with **metadata preamble/footer rows** importers must skip. Download: Płatności → Historia → Zestawienie operacji → CSV. | **Yes, twice**: cp1250 mis-decodes (Polish diacritics garble under ISO-8859-1 fallback); preamble breaks sniffer + header parse |
| **Revolut** | CSV, `Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance`; datetimes `YYYY-MM-DD HH:MM:SS`; has `Currency` column (multi-currency-ready) | **Yes**: rows with `State=REVERTED` (card-verification holds; empty Completed Date/Balance) must be **skipped**, and standard practice is to import only `State=COMPLETED`. No row-filter mechanism exists. Headers are **locale-dependent** (German example documented) — fingerprints must not hardcode English |
| **Wise** | CSV with `TransferWise ID, Date, Amount, Currency, Description, …` — includes a **unique ID column** (ideal for identifier-based dedup); statements limited to 365 days per download; also offers CAMT.053/MT940/QIF | Mostly no — needs a mapping; fee/FX legs appear as separate rows (review once with real file) |

Sources: mBank format spec via accounting-integration docs
([Comarch Betterfly](https://pomoc.comarchbetterfly.pl/dokumentacja/import-przelewow-z-mbanku/),
[mKsiegowa](https://mksiegowa.pl/www/pl/doc/legacy/ImportMbank),
[enova365 guide](https://blog.bst.com.pl/ewidencja-srodkow-pienieznych/eksport-i-import-wyciagow-z-mbanku/)
— third-party accounting docs, not mBank first-party; exact column set should
be confirmed against a real download during implementation). Revolut format:
[beancount discussion](https://groups.google.com/g/beancount/c/jnAZSnzm1Ts)
(includes verbatim REVERTED row),
[homebanking-hilfe on localized headers](https://homebanking-hilfe.de/forum/topic.php?t=27691)
— community sources; confirm with a real export. Wise:
[Wise Help Centre — statements](https://wise.com/help/articles/2736049/how-do-i-download-a-statement),
[transfers list](https://wise.com/help/articles/2489458/how-do-i-download-a-list-of-my-transfers)
(first-party), column list via
[Dativery](https://www.dativery.com/en/apps/wise-csv/).

### 5. Bank auto-detection is cheap

Each bank's header row is a distinctive fingerprint (`Dato;Beløb…` vs
`#Data;#Opis operacji…` vs `Type,Product,Started Date…` vs
`TransferWise ID,…`). Storing a fingerprint (set of expected header names +
delimiter + encoding) per mapping lets the app identify the bank from file
content and eliminate the per-file bank dropdown. Prior art: Firefly III's
community repo of per-bank import configs organized by country/bank
([import-configurations](https://github.com/firefly-iii/import-configurations))
validates the reusable-per-bank-config pattern; its importer auto-generates a
reusable config per import
([JSON config reference](https://docs.firefly-iii.org/references/data-importer/json/)).
Revolut's localized headers mean fingerprints need per-locale variants or a
position-based fallback.

### 6. Web/API state: read-only; pipeline is TUI-only

- API (`src/budget_tracker/api/app.py`): health, transactions, analytics —
  read paths only. No upload, no pipeline, no write endpoints.
- SPA (`web/src/App.tsx` + components): React 18 + ECharts, single read-only
  dashboard (Summary, CategoryChart, MonthlyChart, SourceChart).
- On a home server, the TUI's file-path-based ingestion becomes unusable from
  other devices: statements download to the *browser's* device, so **HTTP
  upload is the required transport**, independent of any UX preference.

### 7. Deployment scope change (supersedes 2026-06-17 decision)

Prior research locked "localhost, single-user, no auth". New target is home
network/server. Implications to settle at design time:
- Bind beyond `127.0.0.1`; serve to LAN or overlay network.
- **Tailscale/VPN-only exposure** would preserve the "no app-level auth"
  simplification; bare-LAN exposure argues for at least a shared token/basic
  auth. (Financial data on an open LAN port is the consideration.)
- Uploads introduce the first write path — CSRF/size limits are trivial but
  nonzero design points once the app leaves localhost.

### 8. What was ruled out

- **Aggregators (GoCardless/Tink/SaltEdge):** declined — third party would
  hold transaction data. (Flow explained: PSD2 AISP consent via bank redirect,
  90/180-day renewals, data transits aggregator cloud.)
- **Eliminating portal visits entirely** (scheduled email statements, e-Boks
  auto-fetch, browser automation): not researched further — user accepted
  monthly manual downloads; per-bank delivery options are mostly PDF-shaped
  and fragile. Can be revisited later per-bank if the monthly download
  becomes the new bottleneck.

## Assessment

The reason the tool went unused is a compounding chain: half the accounts were
never configured (mBank/Revolut/Wise) → partial data makes stats
uninteresting → remaining flow is high-touch per file. Fixing ingestion
mechanics without covering all four banks, or vice versa, won't restore usage;
the two must land together.

Recommended shape (two tracks, roughly independent):

**Track A — ingestion engine (the "why I stopped" fix):**
1. Parser upgrades in `BankMapping`/`CSVParser`: per-mapping `encoding`,
   `delimiter`, `header_row`/skip-preamble, and row filters
   (include/exclude on column value, e.g. `State == COMPLETED`). All four
   banks become parseable.
2. Bank fingerprinting: identify bank from header content; kill the per-file
   bank dropdown. Unknown fingerprint → existing column-mapping flow, saved
   with fingerprint for next time.
3. Rule-based categorization: ordered substring/regex rules → category;
   exact-match cache retained as fast path and seed corpus. Only genuinely
   new merchants prompt.
4. Mappings for mBank, Revolut, Wise (needs one real export from each to
   confirm formats — community sources are consistent but second-hand).

**Track B — web pipeline (the "usable from anywhere" fix):**
5. Upload endpoint + batch processing: files → fingerprint → parse → dedupe →
   transfer detection → rule categorization → pending-review set.
6. One consolidated review screen (uncategorized + ambiguous transfers)
   replacing the TUI's four-screen sequence; then save.
7. Deployment decision: Tailscale-only (recommended — keeps no-auth) vs LAN +
   token auth.

Sizing intuition: Track A items 1–2 are small-to-medium, contained in
parser/models; item 3 is medium (new service + config file); Track B is the
larger lift (first write endpoints + review UI) but was already the known
"Phase 4" of the migration research.

## Suggested Next Steps

- `/rpi:rpi-propose` for the combined feature (or Track A first — it has
  standalone value even used from the TUI, and de-risks Track B).
- Before implementation: obtain one real CSV export from mBank, Revolut, and
  Wise to confirm the second-hand format details (encoding, exact columns,
  REVERTED row shape, Wise fee-row shape).
- At design time: settle Tailscale vs LAN+auth, and whether transfer
  auto-confirmation (pairs matching previously confirmed patterns) is in
  scope for v1.

## Decisions

- **No aggregators — local-only ingestion** (user, 2026-07-17).
- **Monthly manual download per bank is the accepted floor**; everything after
  must be near-zero-touch (user, 2026-07-17).
- **Deployment target is home network/server** — supersedes localhost-only
  scope in the 2026-06-17 research (user, 2026-07-17).
- Banks in scope: **Danske Bank, mBank, Revolut, Wise** (user, 2026-07-17).

## Related Artifacts

- `.rpi/research/2026-06-17-tui-to-local-web-app-migration.md` — prior
  research; its FastAPI+SPA stack decision stands, its localhost-only
  deployment decision is superseded by this document.
- `goals/fastapi-backend-api.md` — completed backend-API milestone spec.
