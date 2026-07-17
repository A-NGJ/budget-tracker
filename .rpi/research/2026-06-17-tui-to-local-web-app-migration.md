---
date: 2026-06-17T18:40:39+02:00
researcher: Claude
git_commit: 7be95bf
branch: main
repository: budget-tracker
topic: "TUI to local web app migration"
tags: [research, migration, web, architecture]
status: active
---

# Research: TUI to local web app migration

## Research Question

What would it take to transform this Textual TUI app into a **local-only,
single-user web application** with a richer UI (interactive charts/dashboards,
mouse-driven interactions like drag-and-drop upload and inline editing)? How much
of the existing Python core carries over, and what's the realistic shape, effort,
and recommended stack?

## Problem Statement

Replace the Textual TUI with a local-only web app (localhost, single-user, data
stays on the machine) whose UI does what a terminal can't — interactive
charts/dashboards and mouse-driven interactions (drag-and-drop CSV upload, inline
editing). Open to a full rewrite of the **presentation layer**. The crux: how much
of the existing Python core (parsers, services, analytics, exporters) is reusable,
and what's the realistic shape + effort + stack choice for the web version.

User-confirmed scope:
- **Deployment:** Local-only, just the user (localhost, single-user, no auth/hosting).
- **Motivation:** Richer visuals (interactive charts) + easier interactions
  (mouse, drag-drop upload, inline editing, forms).
- **Stack appetite:** Open to a full rewrite of the presentation layer.
- **Asked for:** an explicit stack recommendation.

## Summary

**This is a presentation-layer swap, not a rewrite.** The hard, valuable domain
logic (parsing, transfer detection, currency conversion, analytics, categorization
caching, persistence) is cleanly separated from Textual and carries over
essentially untouched. What gets rebuilt is the UI plus the **workflow
orchestration** (the multi-step pipeline currently threaded through TUI screens).

Key structural facts:
- **Zero Textual coupling** in the domain layer.
- **`BudgetService` is already an application-service facade** (~30 methods) — a
  web API wraps this same object.
- **Models are serialization-ready** (pydantic + dataclasses) and the analytics
  output is already shaped like what a charting library consumes.
- **Persistence is local files** (JSON + YAML), no DB — ideal for a local-only app.
- **The one genuinely hard part** is re-modeling the stateful multi-step pipeline
  (`PipelineState` + screen flow), especially the interactive one-by-one
  categorization wizard.

**Recommended stack: FastAPI (wrapping `BudgetService`) + a small SPA**
(Svelte/React) with a charting library (ECharts/Plotly). Pragmatic Python-only
runner-up: **NiceGUI**. Avoid Streamlit-only because its rerun model fights the
categorization wizard.

## Detailed Findings

### 1. Zero Textual coupling in the domain layer

The only UI-framework import anywhere outside `tui/` is `rich` in
`exporters/terminal_renderer.py:6-9` — and that file is a terminal-output renderer
that gets replaced anyway. Nothing in `models/`, `parsers/`, `filters/`,
`currency/`, `analytics/`, `services/`, or `config/` imports `textual`.

> Verified: `grep -rn -E 'import textual|from textual' src/budget_tracker
> --include='*.py' | grep -v '/tui/'` → no matches.

### 2. `BudgetService` is already an application-service facade

`services/budget_service.py:32-251` exposes ~30 public methods covering the entire
feature set, e.g.:
- Ingestion: `detect_columns`, `parse_file`, `load_mapping`, `save_mapping`,
  `list_mappings`
- Processing: `detect_transfers`, `convert_currency`, `create_transaction`,
  `create_transfer_transaction`
- Categorization: `load_categories`, `get_cached_category`, `cache_category`,
  `save_cache`, `clear_cache`
- Analytics/export: `compute_analytics`, `export_excel`, `export_csv`
- Blacklist: `load_bank_blacklist`, `add_blacklist_keyword`,
  `remove_blacklist_keyword`
- Persistence/queries: `save_transactions`, `load_all_transactions`,
  `get_filtered_transactions`, `get_transaction_sources`,
  `get_transaction_categories`, `get_transaction_subcategories`,
  `transaction_count`

The TUI screens are thin consumers. Example: `StatsScreen._recompute`
(`tui/screens/stats.py:256-266`) just calls
`service.get_filtered_transactions(...)` then `service.compute_analytics(...)` and
renders the result. A web API layer would call the exact same methods.

### 3. Models are serialization-ready; analytics is chart-shaped

- Pydantic: `StandardTransaction` (`models/transaction.py`), `BankMapping`
  (`models/bank_mapping.py`), `ParsedTransaction` (`parsers/csv_parser.py:12`).
  These serialize to JSON for free as FastAPI response models.
- Analytics output is structured dataclasses (`analytics/models.py:18-69`):
  `AnalyticsResult` → `SummaryData`, `CategoryRow` (total, percentage, count,
  subcategories), `MonthRow` (income/expenses/net), `SourceRow`. This is exactly
  the shape a charting library consumes.
- Today this same data drives **ASCII bar charts** (`stats.py:295` builds Unicode
  block bars; `plotext` is a dependency). "Richer visuals" = feed the same
  structured data to Plotly/Chart.js/ECharts instead.

### 4. Persistence is local files, no DB

- Transactions: JSON via `services/transaction_store.py:43-66` (atomic write to
  tmp then replace).
- Categories / mappings / category-cache / blacklist: YAML
  (`config/settings.py:44`, `services/budget_service.py:64-73`,
  `services/category_cache.py:35-78`).
- Single-user, on-disk. Binding the web app to `127.0.0.1` means **no auth or
  network-security work**, and the storage layer carries over verbatim.

### 5. The hard part — the stateful multi-step pipeline

`PipelineState` (`tui/state.py:18-42`) is a dataclass threading data across screens:
`files/bank_names/mappings` → `parsed_transactions` → `transfer_pairs`/
`confirmed`/`rejected` → `transactions_to_categorize` →
`categorized_transactions` → `period`/`analytics`.

The screen flow (`tui/app.py:29-39`) is: Home → FileSelection → TransferReview →
PeriodSelection → Categorization (interactive, one-by-one) → Export / Stats.

The **per-step logic** lives in the service; the **orchestration** of the flow and
the interactive categorization loop live in the TUI and have no direct analog in a
web app. This must be re-modeled as either server-side session state or
client-side SPA state. The read-only analytics/stats dashboard, by contrast, is
trivial to port.

### What carries over vs. gets rebuilt

| Reused ~as-is | Rebuilt / new |
|---|---|
| `models/`, `parsers/`, `filters/`, `currency/`, `analytics/`, `services/`, `config/`, `exporters/excel_exporter.py` + `csv_exporter.py`, all persistence (JSON/YAML), and their tests | Entire `tui/` dir + `exporters/terminal_renderer.py` |
| | Web API layer (wrap `BudgetService`) |
| | Frontend UI (charts, forms, drag-drop, inline edit) |
| | Pipeline/session orchestration (replacing `PipelineState` + screen flow) |

Small cleanup during migration: some reusable logic currently sits in the TUI —
e.g. `_period_to_dates` period presets at `tui/screens/stats.py:76-103` — and
should move down into the service/analytics layer so both the API and any future
client share it.

## Assessment

### Stack options

| Option | UI ceiling | Reuses core | Effort | Notes |
|---|---|---|---|---|
| **FastAPI + SPA** (Svelte/React) + ECharts/Plotly | highest | direct (JSON API) | High | Best for interactive charts, drag-drop, inline edit. Two codebases + JS build chain. |
| **NiceGUI** (Python-only; Vue/Quasar under hood) | high | direct (in-process) | Medium | Real components + interactivity, no JS build, handles the stateful wizard well. Pragmatic sweet spot. |
| **Streamlit / Dash** | medium (Dash charts: high) | direct | Low–Med | Great for the stats dashboard; rerun model fights the multi-step categorization wizard. |

> Framework characteristics are well-established general knowledge as of mid-2026;
> pull current official docs for the chosen framework before design work.

### Recommendation

- **Best UI / don't mind JS → FastAPI wrapping `BudgetService` + a small
  Svelte/React SPA** with a charting library. Best ceiling for "richer visuals +
  easier interactions"; cleanly reuses the entire Python core.
- **Stay Python-only → NiceGUI.** Reuses the core in-process, no second toolchain,
  and handles the stateful categorization wizard far better than Streamlit.
- **Steer away from Streamlit-only** specifically because of the categorization
  wizard's rerun-model friction.

**Chosen direction (2026-06-17):** FastAPI + SPA.

### Suggested migration shape (phased)

1. **Extract stray UI-layer logic** down into services/analytics (e.g.
   `_period_to_dates`). Small.
2. **Backend API** — FastAPI app wrapping `BudgetService`; endpoints mirror the
   read methods; reuse pydantic models as response schemas. *(First milestone —
   see goal below.)*
3. **Stats dashboard (read-only)** — SPA shell + charts from analytics data.
   Quickest win, highest visual payoff.
4. **Interactive pipeline** — upload → column mapping → transfer review →
   categorization wizard → save; model session state server- or client-side
   (replaces `PipelineState` + screen flow). Hardest phase.
5. **Settings/mappings/blacklist** management screens.

Serving: FastAPI + uvicorn on `127.0.0.1`, open a browser; could ship as a
`budget-tracker serve` subcommand. No auth needed.

## Suggested Next Steps

- Proceed via `/rpi:rpi-propose` to design the FastAPI + SPA migration (or design
  per-phase).
- Define follow-up `/goal` milestones off the phased shape above:
  - **Phase 2 (backend API, read paths)** — already compiled into a goal; spec at
    `goals/fastapi-backend-api.md`.
  - **Phase 3 (stats dashboard SPA)** — next goal to define.
  - **Phase 4 (interactive pipeline/wizard)** — likely split into multiple goals.

## Decisions

- **Local-only, single-user** target → bind to localhost, no auth, file-based
  persistence reused verbatim.
  - **Superseded 2026-07-17:** deployment target is now home network/server
    (LAN or Tailscale, reachable from phone + laptop). See
    `.rpi/research/2026-07-17-low-friction-local-only-ingestion-and-web-pipeline-completion.md`.
- **Full rewrite of the presentation layer only** — domain layer is reused as-is.
- **Stack: FastAPI + SPA** (Svelte/React) + charting library; NiceGUI is the
  Python-only fallback.
- **First implementation milestone = backend API, read paths only** (additive,
  no changes to domain or TUI). Compiled goal spec: `goals/fastapi-backend-api.md`.

## Related Artifacts

- `goals/fastapi-backend-api.md` — compiled `/goal` spec for the backend-API
  milestone (Phase 2).
