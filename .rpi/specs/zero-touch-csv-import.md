---
domain: ingestion
feature: zero-touch-csv-import
last_updated: 2026-07-17T14:55:00+02:00
updated_by: .rpi/designs/2026-07-17-zero-touch-csv-import-engine.md
---

# Zero-touch CSV import

## Purpose

Importing bank statements is a single non-interactive command: files from any
of the four supported banks (Danske Bank, mBank, Revolut, Wise) are
recognized, parsed, deduplicated, transfer-matched, and categorized by
user-authored rules — with no per-file or per-transaction questions.

## Scenarios

### Import identifies each bank automatically
Given statement files downloaded from Danske Bank, mBank, Revolut, and Wise
When the user imports them all in one command
Then every file is processed under the correct bank without the user naming a bank for any file

### Polish bank statements parse correctly
Given an mBank statement export in its native form (national character
encoding, semicolon separators, metadata lines before and after the
transaction table)
When the user imports it
Then its transactions are saved with Polish characters intact and correct
dates and amounts, and the metadata lines are ignored

### Reverted card holds are excluded
Given a Revolut statement containing reverted (never-completed) entries
alongside completed transactions
When the user imports it
Then only the completed transactions are saved and the reverted entries are
absent

### Known merchants categorize silently
Given a categorization rule mapping a description pattern to a category
When the user imports a statement containing transactions matching that
pattern
Then those transactions are saved with that category and the import asks no
questions

### Unknown merchants are reported, then fixed by a rule
Given an imported transaction whose description matched no rule and no prior
assignment, so it was saved as "Uncategorized" and its description appeared
in the import summary
When the user adds a matching rule and runs the recategorize command
Then that transaction now carries the rule's category and the command reports
how many transactions changed

### Cross-bank transfers are excluded automatically
Given one import containing a matching pair — same day, same amount, one
outgoing and one incoming, from two different banks
When the user imports the files
Then the pair is recorded as an internal transfer, excluded from spending
statistics, and no confirmation is requested

### Re-importing overlapping statements is safe
Given statements covering a period that was already imported
When the user imports them again
Then no duplicate transactions appear and the summary reports how many rows
were skipped as already present

### An unrecognized file does not block the batch
Given a batch of files including one from an unsupported source
When the user imports the batch
Then the recognized files import normally, the unrecognized file is reported
by name with nothing imported from it, and the command signals failure

## Constraints

- Statement contents never leave the machine; no third-party service takes
  part in ingestion.
- The import and recategorize commands never prompt; they are safe to run
  unattended.
- Rules and bank format definitions are plain, user-editable files; edits
  take effect on the next run without reinstalling.
- Every saved transaction carries a valid category; "Uncategorized" is
  always valid, including for installs configured before it existed.
- Importing never alters previously saved transactions; only the
  recategorize command may change them, and only those marked
  "Uncategorized".
- An invalid categorization rule (unknown category) is reported by name, not
  silently ignored.
- The existing terminal UI keeps working; the only difference a terminal
  user sees is that more transactions arrive already categorized (rules now
  apply there too).

## Out of Scope

- Uploading files or reviewing imports through the web app (Track B).
- Removing the terminal UI.
- Authoring rules through a UI.
- Undoing or reviewing auto-confirmed transfers.
- Fetching statements from banks automatically.
- Deleting transactions.
