# Private desktop web redesign

Status: product and frontend design approved by the operator on 2026-10-03. Frontend alignment is complete: use A/Desk with the approved per-item inbox and transaction-context transfer review. This document does not authorize provisioning, commits, or deployment.

## Scope and access

- Desktop web interface; no TUI or mobile requirement.
- Ordinary browser access from the operator's trusted desktops, without requiring an installed application or VPN.
- Initially for the operator alone.
- Prefer established cloud providers such as Google Cloud. Target free hosting, with approximately €5/month acceptable for a meaningful reliability benefit. No always-on home machine required.
- Focus on spending analysis, month-to-month comparison, and recurring costs, rather than active budget limits or net-worth tracking.
- Re-import historical CSV statements rather than migrate the existing transaction store. Existing data and implementation are not authorized for deletion.
- Manual statement downloads with reusable statement profiles for adding formats.
- Initial banks are Danske Bank, mBank, and Revolut; no bank is missing from that list. Adding further banks remains supported through statement profiles.
- Provide a visual statement-profile editor. Open and parse the sample CSV locally, map its fields and format, preview transactions, and save a reusable profile. Profiles can be imported/exported for reuse.
- Support current desktop Chrome, Edge, Firefox, and Safari. Use a clean, data-dense interface, restrained chart colors, system light/dark mode, and keyboard-accessible controls.

## Privacy and identity

- Store financial history encrypted in the cloud. Decrypt and process it in the trusted browser; cloud storage must not receive the financial-history decryption key.
- Trust Google to deliver the application code correctly. The operator accepts that client-side encryption does not prevent a malicious application-code deployment from capturing unlocked information.
- Use Google sign-in for access and a separate passphrase to unlock financial data on a new desktop.
- Provide an offline recovery key that the operator can keep in a password manager. If both the passphrase and recovery key are lost, cloud data cannot be recovered by resetting the Google account; re-importing statements is the fallback.
- Unlock on each fresh application load, lock after 15 minutes of inactivity, and provide a manual lock action. Readable records and decryption keys remain in memory only; any persistent browser cache is encrypted and cleared on sign-out.
- Allow passphrase changes and recovery-key regeneration without re-importing financial history.
- Jev may receive a single record's normalized merchant label and bank-provided spending label when available. Exclude amounts, dates, account identifiers, bank names, transaction references, people's names, and free-form payment messages. If permitted text cannot be confidently extracted, keep the transaction local for human classification. Merchant-level purchase information is explicitly allowed to be disclosed.
- Use an authenticated Google-hosted classification relay with the operator's Jev API key held server-side. Both the relay and Jev see the approved text. The relay cannot decrypt financial history, does not log request bodies, is restricted to the operator's signed-in account, and limits requests.
- The full financial history remains encrypted; the classification exception does not authorize sending raw statements, full transactions, or decryption keys. See `docs/adr/0001-encrypted-history-with-text-only-classification.md`.

## Financial model

- Track individual accounts and currency balances, including multiple accounts at one bank.
- Preserve original transaction amounts and currencies; report totals in DKK.
- Own-account transfers produce neither income nor spending.
- Refunds reduce spending in the original purchase category in the month the refund arrives.
- Savings and investment contributions appear separately from everyday spending.
- Count outgoing savings contributions once even when both sides are imported. Returning money from savings is not income.
- Treat cash withdrawals as cash spending under Other initially, retaining their cash-withdrawal type and without a separate cash-purchase ledger.
- Categories are flat. Initial list: Home, Groceries, Eating out, Transport, Shopping, Leisure, Travel, Health, Financial costs, Other.
- Income, transfers, and contributions are transaction types, not spending categories.
- Recurring status is independent of category. Recurring costs are ongoing payment commitments, including variable bills and annual renewals, excluding repeated discretionary purchases.

## Classification and review

- Apply remembered merchant choices first, rules second, and Jev for unfamiliar merchants with permitted text.
- Accept reliable model results automatically only after validating the confidence threshold on the operator's statement data. Uncertain classifications remain unresolved for human review.
- Provide one in-app review inbox with separate sections and counts for uncategorized transactions, ambiguous transfers, and recurring-cost suggestions. Other is a deliberate category, not the unresolved state.
- Offer to remember a category correction for future transactions from the same merchant.
- Jev failure or unavailability does not block imports; unfamiliar transactions remain uncategorized.
- Give each inbox transaction its own category selector and assignment action; do not require checkboxes and a shared bottom selector. Explain why each item requires attention. Remembering a merchant decision is an explicit per-item choice.
- Transfer review shows both candidate transactions with dates, accounts, descriptions/references, signed original amounts, and DKK conversion where needed. Offer confirm-transfer and not-a-transfer actions.
- Uncategorized spending remains included in spending totals and visible as unresolved, rather than being omitted.

## Importing and conversion

- Preserve original CSV statements encrypted alongside financial history, with an option to delete them.
- Preview imports, duplicates, and parsing errors before saving. Overlapping statements must not create duplicate transactions.
- Provide an account selector per file in the preview. Remember verified account identifiers where available; otherwise ask the operator to select or create an account rather than infer identity from a bank name or filename.
- Statement profiles identify formats independently of accounts. Accounts at the same bank may share a format. Resolve multi-currency Revolut records to separate currency balances.
- Never silently skip parsing errors or collapse uncertain duplicates. Show problematic rows locally; allow profile correction and reparsing, or explicit approval to import only valid rows.
- Prefer bank transaction IDs for deduplication when available, recognize exact file re-imports, and require confirmation for uncertain duplicate candidates. Equal merchant/date/amount values alone do not prove that two genuine purchases are one transaction.
- Save the confirmed import atomically; failure must not leave a half-imported batch.
- Use public historical daily exchange rates for reporting conversion, with the previous available rate on weekends and holidays. Downloading rates may disclose requested currencies and date ranges, but not descriptions or amounts. Missing rates leave DKK totals visibly incomplete.
- Reconsider earlier transactions when a later import supplies the other side of a transfer.
- Automatically match only unambiguous equal-and-opposite same-currency movements between the operator's accounts within a three-calendar-day window. Cross-currency and ambiguous matches require review.
- Allow manual transfer marking and undo, including one-sided transfers.

## Interface and reporting

- Overview shows the selected month's spending, change from the previous month, category breakdown, 12-month spending trend, and recurring-cost summary.
- Open the latest month with imported transactions and show statement coverage. Flag comparisons involving incomplete periods.
- Transactions provides search, filters, and category/type editing. Clicking a category or chart opens its corresponding transactions.
- Inbox contains unresolved decisions; Recurring contains confirmed commitments and their history.
- Import statements is available from every page; settings stay outside the main navigation.
- Use the selected A/Desk layout: persistent sidebar navigation, compact summary cards, category breakdown, and upcoming-payment panels.
- Category and type can be edited on any transaction, with undo and preservation of the original bank record.
- Initially no split transactions. Support category addition, renaming, and merging, carrying existing transactions across.
- Unresolved transaction types make affected reports visibly provisional; missing conversion rates and incomplete statement coverage must not produce apparently complete comparisons.

## Recurring costs

- Suggest possible commitments from history and require human confirmation.
- Record cadence, expected amount, and next payment date. Estimate next-30-day costs and annual totals.
- Distinguish fixed amounts from variable estimates. Allow commitments to be edited, paused, or ended without removing their history.
- Fixed estimates use the confirmed amount and cadence. Variable estimates are suggested from the last three comparable payments and can be overridden.
- Annual totals project currently active commitments rather than summarize historical spending. Future foreign-currency costs use the latest available rate and are labeled estimates.
- Allow manual commitment creation before enough payment history exists for detection.

## Hosting and synchronization

- Use Firebase Hosting, Firebase Authentication with Google sign-in, Firestore encrypted storage, and a Cloud Run classification relay. Prefer EU locations for stored history and the relay. See ADR-0002.
- The operator accepts billing-enabled Google hosting with free/very-low-cost usage as the target, not a guaranteed cap. Use no always-running relay instances, restricted classification requests, and a €5 budget alert.
- Automatically synchronize encrypted data across desktops. Initially support online-only editing, not offline writes.
- An already-open app may show its current data during an outage, but must clearly prevent unsaved changes from appearing saved.
- Detect stale edits from another desktop. Reload or resolve a conflict rather than silently overwriting newer decisions.

## Backup and portability

- Download a complete encrypted backup containing history, corrections, profiles, recurring commitments, and retained statements.
- Preview restoration and require explicit confirmation before replacing existing data.
- Export selected transactions to CSV, clearly identifying it as an unencrypted download.
- Keep the recovery key separately from the backup.

## Verified starting point

- React/TypeScript/Vite frontend and FastAPI backend already exist, including import/review work and TUI removal.
- Existing bank support covers Danske Bank, mBank, and Revolut. The operator has confirmed these as the complete initial bank list.
- Existing classification uses exact-description assignments and ordered rules, not a model.
- Existing transaction records lack original currency amounts, account identity, and full import provenance.
- Existing Python-server processing does not meet the new encrypted-storage boundary without redesign.
- Initial Python baseline on 2026-10-03: `.venv/bin/python -m pytest tests/ -q`, 232 passed with four deprecation warnings. This was measured before later repository updates during the interview; no application code has been changed by this design session.

## Primary-source findings

### Jev

Jev is a hosted classifier accepting text and typed questions. Choice questions accept supplied labels and return a choice, per-label probabilities, and confidence. The documented SDKs call a hosted API; no published browser-local runtime or downloadable weights were found. The agreed text-only exception permits external classification through the authenticated relay.

The JavaScript SDK refuses browser execution by default because it exposes the API key. Vendor guidance is to keep credentials server-side. Documented pricing is $0.042 per million input tokens, with output tokens free; free allowance, signup requirements, and minimum charges were not verified. Early access remains a dependency. Confidence thresholds need validation on actual statement descriptions rather than treating them as accuracy guarantees.

Sources:

- https://typesafe.ai/blog/introducing-system-one-models-and-jev
- https://docs.typesafe.ai/models.md
- https://docs.typesafe.ai/primitives/choice.md
- https://docs.typesafe.ai/confidence.md
- https://docs.typesafe.ai/sdk/javascript.md
- https://typesafe.ai/legal/privacy-policy

### Google hosting

Firebase Hosting, Authentication, and Firestore have no-cost Spark allowances. Firestore documents are limited to 1 MiB, affecting encrypted storage layout. Cloud Storage for Firebase requires billing-enabled Blaze; its free storage allowance has US-region restrictions. Ordinary billing alerts do not enforce a €5 spending ceiling. The operator selected Hosting, Authentication, Firestore, and Cloud Run with EU history storage and relay locations where configurable.

Cloud Run requires a linked billing account; linking one upgrades a Firebase project from Spark to Blaze. Request-based Cloud Run has no-cost allowances, and Firebase Hosting can route to a relay in an EU region such as `europe-west1`. Minimum instances of zero, low maximum instances, and application request limits can reduce costs but do not enforce a €5 infrastructure ceiling. Personal compute usage may fit the allowances; total cost also depends on storage, network traffic, deployment artifacts, and other services. Billing-enabled hosting was accepted in round four; provisioning remains outside this interview.

Sources:

- https://firebase.google.com/pricing
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/storage/faqs-storage-changes-announced-sept-2024
- https://firebase.google.com/docs/projects/billing/spend-caps
- https://firebase.google.com/docs/hosting/cloud-run
- https://cloud.google.com/run/pricing
- https://cloud.google.com/secret-manager/pricing
- https://firebase.google.com/docs/firestore/locations

## Engineering choices within the product constraints

These choices remain for implementation planning rather than another product interview:

- Browser encryption libraries, key wrapping and derivation, encrypted record/chunk layout, and format versioning. Preserve browser-only decryption, recovery, atomic imports, and conflict detection.
- Concrete Google regions and deployment settings within the agreed EU storage/relay preference and low-cost operating target.
- Public exchange-rate provider selection and caching that supports required currencies, historical dates, previous-rate fallback, and visibly incomplete conversion.
- Profile schema and editor controls for required CSV variants, account/currency identity, date interpretation, and bank transaction IDs. Validate profiles against representative exports locally rather than assuming existing examples are authoritative.
- Conservative merchant extraction and relay payload enforcement. Raw descriptions are not automatically eligible for transmission, and inability to establish permitted text must lead to human review.
- Confidence thresholds, recurring-detection heuristics, and exact variable-estimate statistics, validated against representative data while preserving the human-review and override behavior.
- UI component, chart, and storage libraries meeting the agreed browser support, accessibility, and reporting interactions.

Jev account availability, billing details beyond published token pricing, and real-export validation remain external verification items. They do not change the fallback requirement: the operator can import, inspect, and classify transactions without Jev.

## Design confirmation

All stated product choices are resolved. The operator confirmed the consolidated design, selected A/Desk through the frontend prototype, and approved the revised inbox. The design is ready for implementation planning. A new requirement or discovered contradiction reopens the relevant decision before implementation.

## Frontend alignment prototype

Question: which information hierarchy and interaction style fits monthly spending review? Three development-only variants live beside the frontend in `web/src/components/prototype/`, on the existing route with `?prototype=web&variant=A|B|C`.

- A, Desk: sidebar dashboard with summary cards and category/upcoming-payment panels.
- B, Report: horizontal navigation and an editorial monthly overview.
- C, Ledger: icon rail and transaction-first layout with adjacent analysis.

Run `npm run prototype` from `web/`. Synthetic, in-memory interactions cover transactions, review, recurring commitments, and an illustrative import/profile-editor flow. Prototype code is not a production implementation.

### Operator feedback

- Selected A/Desk as the preferred frontend direction.
- Requested individual category assignment per inbox item instead of checkbox selection and a shared category selector.
- Transfer review lacked transaction context; show both candidate records and their amounts/accounts/dates before asking for a decision.
- Explicitly liked the recurring-suggestion widget; carry that interaction into the chosen design.
- Approved the revised inbox with "yes that looks good". The frontend alignment question is settled: implement A/Desk with individual category assignment, visible transfer candidates, and the recurring-suggestion widget.

The revised inbox prototype implements this feedback. Transfer review uses a separate synthetic example pair; confirming or rejecting it resolves the demo card without changing the ledger totals. The full variant set remains available as a primary source until archival on a throwaway branch is explicitly authorized.

Revised-inbox verification: independent row selections and assignments work without checkboxes; assigning one record preserves another record's selection. Both transfer candidates are visible and confirm/reject actions resolve the card. Recurring confirmation still works, and the pending count reaches zero after review. Browser inspection found no runtime errors, backend requests, or horizontal overflow at 1280px; frontend typecheck and production build passed.

Verification: frontend typecheck and production build passed. Browser inspection covered all three layouts at desktop widths, category review, recurring confirmation/pause, profile mapping, simulated imports, transaction search/edit/undo, theme changes, and URL/keyboard variant switching. No browser runtime errors or backend API requests were observed. Production builds exclude the prototype module and styles.

Domain definitions are recorded in `CONTEXT.md`. ADR-0001 records the encrypted-history and text-only-classification boundary; ADR-0002 records Google managed hosting, EU storage, and the accepted billing trade-off.
