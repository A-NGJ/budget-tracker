# Budget Tracker

A TUI tool to standardize bank statements and categorize transactions interactively.

## Features

- Process CSV bank statements from multiple banks
- Interactive transaction categorization in the TUI, with cached suggestions for descriptions you've categorized before
- Interactive column mapping for new bank formats
- Currency conversion to DKK
- Export to standardized CSV format

## Requirements

- Python 3.12+

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd budget-tracker

# Install with uv
uv sync
```

## Usage

### Process bank statements

```bash
# Process a single file
budget-tracker process statement.csv --banks mybank

# Process multiple files
budget-tracker process bank1.csv bank2.csv --banks bankA --banks bankB

# Specify output file
budget-tracker process statement.csv --banks mybank --output results.csv
```

### List saved bank mappings

```bash
budget-tracker list-mappings
```

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

## How It Works

1. **Parse** - Reads CSV files and maps columns to standard fields (date, amount, description)
2. **Categorize** - Assign a category to each transaction in the TUI; previously categorized descriptions are applied automatically from the cache
3. **Convert** - Converts amounts to DKK
4. **Review** - Lets you review and adjust assignments before export
5. **Export** - Outputs standardized CSV

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
pytest

# Type checking
ty check

# Linting
ruff check

# Formatting
ruff format --check
```

## Project Structure

```
src/budget_tracker/
├── analytics/     # Spending analysis
├── config/        # Settings and configuration
├── currency/      # Currency conversion
├── exporters/     # Output formatters
├── filters/       # Transaction filtering
├── models/        # Data models
├── parsers/       # CSV parsing
├── services/      # Categorization, storage, budgets
└── tui/           # Terminal UI (categorization, review, export)
```
