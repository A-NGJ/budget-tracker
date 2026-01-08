# Internal Transfer Detection Implementation Plan

## Overview
Detect and mark internal transfers between bank accounts to prevent them from polluting budget spreadsheets. Internal transfers appear as matching +/- amounts on the same day across different accounts. Users will confirm detected transfers interactively before they're marked as "Internal Transfer" category.

## Current State Analysis

### Transaction Processing Pipeline (`src/budget_tracker/cli/main.py:42`)
```
Parse CSVs → Categorize with LLM → Confirm uncertain → Export
```

### Key Discoveries:
- `ParsedTransaction` contains: `date`, `amount`, `currency`, `description`, `source` (bank name) - `csv_parser.py:12`
- `StandardTransaction` contains categorization info and `transaction_id` property - `transaction.py:13`
- Interactive confirmation pattern exists in `confirmation.py:10` using Rich prompts
- Multiple bank files are processed together in `all_parsed_transactions` list - `main.py:90`

### Current Categories (`config/categories.yaml`)
- No "Internal Transfer" category exists
- Categories are validated against this file in `transaction.py:26`

## Desired End State

1. **New category** "Internal Transfer" with subcategory "Transfer" in categories.yaml
2. **Automatic detection** of transfer pairs (same absolute amount, opposite signs, same date, different sources)
3. **Interactive confirmation** showing detected pairs, user confirms each
4. **Confirmed transfers** skip LLM categorization and are marked as "Internal Transfer"
5. **Declined pairs** proceed through normal LLM categorization

### Verification:
- Process two bank statements with a transfer between them
- System detects the transfer pair and prompts for confirmation
- Confirmed transfers appear in output with category "Internal Transfer"
- Google Sheets/CSV export shows transfers correctly categorized

## What We're NOT Doing

- Partial amount matching (e.g., transfers with fees)
- Cross-day matching (must be same day)
- Automatic removal of transfers (we keep them, just categorize differently)
- Description-based matching (amount only)
- Transfer detection within same bank account (requires different sources)

## Implementation Approach

Detection happens **after parsing but before LLM categorization**:
```
Parse CSVs → DETECT TRANSFERS → Categorize non-transfers with LLM → Confirm uncertain → Export
```

This saves LLM API calls for confirmed transfers.

---

## Phase 1: Add Internal Transfer Category

### Overview
Add the new category to categories.yaml so it can be used for transfers.

### Changes Required:

#### 1. Update categories configuration
**File**: `config/categories.yaml`
**Changes**: Add "Internal Transfer" category after "Income"

```yaml
  - name: "Internal Transfer"
    subcategories:
      - "Transfer"
```

### Success Criteria:

#### Automated Verification:
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] Category appears in categories.yaml
- [x] Existing tests still pass

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 2: Create Transfer Detection Logic

### Overview
Create a new module to detect matching transfer pairs from parsed transactions.

### Changes Required:

#### 1. Create transfer detector module
**File**: `src/budget_tracker/filters/__init__.py` (new)
**Changes**: Create package init

```python
"""Transaction filtering modules."""

from budget_tracker.filters.transfer_detector import TransferDetector, TransferPair

__all__ = ["TransferDetector", "TransferPair"]
```

#### 2. Create transfer detector implementation
**File**: `src/budget_tracker/filters/transfer_detector.py` (new)
**Changes**: Implement transfer detection algorithm

```python
"""Detect internal transfers between bank accounts."""

from collections import defaultdict
from decimal import Decimal

from pydantic import BaseModel

from budget_tracker.parsers.csv_parser import ParsedTransaction


class TransferPair(BaseModel):
    """A matched pair of transactions representing an internal transfer."""

    outgoing: ParsedTransaction  # Negative amount (money leaving)
    incoming: ParsedTransaction  # Positive amount (money arriving)

    @property
    def amount(self) -> Decimal:
        """Absolute transfer amount."""
        return abs(self.outgoing.amount)


class TransferDetector:
    """Detect internal transfers between different bank accounts."""

    def detect(
        self, transactions: list[ParsedTransaction]
    ) -> tuple[list[TransferPair], list[ParsedTransaction]]:
        """
        Detect internal transfer pairs from a list of transactions.

        A transfer pair is identified when:
        - Two transactions have the same absolute amount
        - One is positive, one is negative
        - They occur on the same date
        - They come from different bank sources

        Args:
            transactions: List of parsed transactions from multiple banks

        Returns:
            Tuple of (detected transfer pairs, remaining non-transfer transactions)
        """
        # Group transactions by (date, absolute_amount)
        groups: dict[tuple, list[ParsedTransaction]] = defaultdict(list)
        for t in transactions:
            key = (t.date, abs(t.amount))
            groups[key].append(t)

        transfer_pairs: list[TransferPair] = []
        matched_indices: set[int] = set()

        # Find matching pairs
        for group in groups.values():
            if len(group) < 2:
                continue

            # Separate positive and negative transactions
            positive = [t for t in group if t.amount > 0]
            negative = [t for t in group if t.amount < 0]

            # Match pairs from different sources
            for neg in negative:
                for pos in positive:
                    # Must be from different banks
                    if neg.source == pos.source:
                        continue

                    # Check if already matched
                    neg_idx = transactions.index(neg)
                    pos_idx = transactions.index(pos)
                    if neg_idx in matched_indices or pos_idx in matched_indices:
                        continue

                    # Found a pair
                    transfer_pairs.append(TransferPair(outgoing=neg, incoming=pos))
                    matched_indices.add(neg_idx)
                    matched_indices.add(pos_idx)
                    break  # Move to next negative transaction

        # Remaining transactions (not part of any transfer)
        remaining = [t for i, t in enumerate(transactions) if i not in matched_indices]

        return transfer_pairs, remaining
```

#### 3. Create unit tests for transfer detector
**File**: `tests/unit/test_transfer_detector.py` (new)
**Changes**: Test transfer detection logic

```python
"""Tests for transfer detection."""

from datetime import date
from decimal import Decimal

import pytest

from budget_tracker.filters.transfer_detector import TransferDetector, TransferPair
from budget_tracker.parsers.csv_parser import ParsedTransaction


def make_transaction(
    amount: Decimal,
    source: str,
    tx_date: date | None = None,
    description: str = "Test",
) -> ParsedTransaction:
    """Helper to create test transactions."""
    return ParsedTransaction(
        date=tx_date or date(2024, 1, 15),
        amount=amount,
        currency="DKK",
        description=description,
        source=source,
        source_file="test.csv",
    )


class TestTransferDetector:
    """Tests for TransferDetector."""

    def test_detect_simple_transfer(self) -> None:
        """Detect a simple transfer between two banks."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_b"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 1
        assert len(remaining) == 0
        assert pairs[0].amount == Decimal("100.00")
        assert pairs[0].outgoing.source == "bank_a"
        assert pairs[0].incoming.source == "bank_b"

    def test_no_transfer_same_bank(self) -> None:
        """Don't match transactions from the same bank."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_a"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_no_transfer_different_dates(self) -> None:
        """Don't match transactions on different dates."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a", date(2024, 1, 15)),
            make_transaction(Decimal("100.00"), "bank_b", date(2024, 1, 16)),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_no_transfer_different_amounts(self) -> None:
        """Don't match transactions with different amounts."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("99.00"), "bank_b"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 0
        assert len(remaining) == 2

    def test_mixed_transactions(self) -> None:
        """Correctly separate transfers from regular transactions."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),  # Transfer out
            make_transaction(Decimal("100.00"), "bank_b"),   # Transfer in
            make_transaction(Decimal("-50.00"), "bank_a"),   # Regular expense
            make_transaction(Decimal("200.00"), "bank_a"),   # Regular income
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 1
        assert len(remaining) == 2
        assert pairs[0].amount == Decimal("100.00")

    def test_multiple_transfers(self) -> None:
        """Detect multiple transfers correctly."""
        transactions = [
            make_transaction(Decimal("-100.00"), "bank_a"),
            make_transaction(Decimal("100.00"), "bank_b"),
            make_transaction(Decimal("-200.00"), "bank_b"),
            make_transaction(Decimal("200.00"), "bank_c"),
        ]

        detector = TransferDetector()
        pairs, remaining = detector.detect(transactions)

        assert len(pairs) == 2
        assert len(remaining) == 0

    def test_transfer_pair_amount_property(self) -> None:
        """TransferPair.amount returns absolute value."""
        pair = TransferPair(
            outgoing=make_transaction(Decimal("-150.00"), "bank_a"),
            incoming=make_transaction(Decimal("150.00"), "bank_b"),
        )

        assert pair.amount == Decimal("150.00")
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_transfer_detector.py -v`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] TransferDetector correctly identifies transfer pairs
- [x] Non-transfer transactions are preserved in remaining list

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 3: Add Interactive Confirmation

### Overview
Create a UI component to show detected transfers and let users confirm or reject each pair.

### Changes Required:

#### 1. Create transfer confirmation module
**File**: `src/budget_tracker/cli/transfer_confirmation.py` (new)
**Changes**: Interactive confirmation for detected transfers

```python
"""Interactive confirmation for detected internal transfers."""

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from budget_tracker.filters.transfer_detector import TransferPair

console = Console()


def confirm_transfers(
    pairs: list[TransferPair],
) -> tuple[list[TransferPair], list[TransferPair]]:
    """
    Show detected transfers and ask user to confirm each.

    Args:
        pairs: List of detected transfer pairs

    Returns:
        Tuple of (confirmed pairs, rejected pairs)
    """
    if not pairs:
        return [], []

    console.print(f"\n[cyan]Detected {len(pairs)} potential internal transfer(s):[/cyan]")

    confirmed: list[TransferPair] = []
    rejected: list[TransferPair] = []

    for i, pair in enumerate(pairs, 1):
        # Display transfer details
        table = Table(title=f"Transfer {i}/{len(pairs)}", show_header=True)
        table.add_column("Direction", style="cyan")
        table.add_column("Date")
        table.add_column("Amount")
        table.add_column("Bank")
        table.add_column("Description")

        table.add_row(
            "OUT",
            str(pair.outgoing.date),
            f"{pair.outgoing.amount:.2f} {pair.outgoing.currency}",
            pair.outgoing.source,
            pair.outgoing.description[:40] + "..." if len(pair.outgoing.description) > 40 else pair.outgoing.description,
        )
        table.add_row(
            "IN",
            str(pair.incoming.date),
            f"{pair.incoming.amount:.2f} {pair.incoming.currency}",
            pair.incoming.source,
            pair.incoming.description[:40] + "..." if len(pair.incoming.description) > 40 else pair.incoming.description,
        )

        console.print(table)

        choice = Prompt.ask(
            "Mark as internal transfer?",
            choices=["y", "n", "a", "s"],
            default="y",
        )

        if choice == "y":
            confirmed.append(pair)
            console.print("[green]Marked as internal transfer[/green]")
        elif choice == "n":
            rejected.append(pair)
            console.print("[yellow]Will categorize normally[/yellow]")
        elif choice == "a":
            # Accept all remaining
            confirmed.append(pair)
            confirmed.extend(pairs[i:])
            console.print(f"[green]Marked {len(pairs) - i + 1} transfer(s) as internal[/green]")
            break
        else:  # skip all
            rejected.append(pair)
            rejected.extend(pairs[i:])
            console.print(f"[yellow]Skipping {len(pairs) - i + 1} pair(s)[/yellow]")
            break

    return confirmed, rejected
```

#### 2. Create tests for transfer confirmation
**File**: `tests/unit/test_transfer_confirmation.py` (new)
**Changes**: Test the confirmation logic (mocking user input)

```python
"""Tests for transfer confirmation UI."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from budget_tracker.cli.transfer_confirmation import confirm_transfers
from budget_tracker.filters.transfer_detector import TransferPair
from budget_tracker.parsers.csv_parser import ParsedTransaction


def make_pair(amount: Decimal = Decimal("100.00")) -> TransferPair:
    """Helper to create test transfer pairs."""
    return TransferPair(
        outgoing=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=-amount,
            currency="DKK",
            description="Transfer to savings",
            source="bank_a",
            source_file="test.csv",
        ),
        incoming=ParsedTransaction(
            date=date(2024, 1, 15),
            amount=amount,
            currency="DKK",
            description="Transfer from checking",
            source="bank_b",
            source_file="test.csv",
        ),
    )


class TestConfirmTransfers:
    """Tests for confirm_transfers function."""

    def test_empty_list(self) -> None:
        """Empty list returns empty results."""
        confirmed, rejected = confirm_transfers([])
        assert confirmed == []
        assert rejected == []

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_confirm_single(self, mock_print, mock_ask) -> None:
        """Confirming a single transfer."""
        mock_ask.return_value = "y"
        pairs = [make_pair()]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 1
        assert len(rejected) == 0

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_reject_single(self, mock_print, mock_ask) -> None:
        """Rejecting a single transfer."""
        mock_ask.return_value = "n"
        pairs = [make_pair()]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 0
        assert len(rejected) == 1

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_accept_all(self, mock_print, mock_ask) -> None:
        """Accept all remaining transfers."""
        mock_ask.return_value = "a"
        pairs = [make_pair(Decimal("100")), make_pair(Decimal("200")), make_pair(Decimal("300"))]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 3
        assert len(rejected) == 0

    @patch("budget_tracker.cli.transfer_confirmation.Prompt.ask")
    @patch("budget_tracker.cli.transfer_confirmation.console.print")
    def test_skip_all(self, mock_print, mock_ask) -> None:
        """Skip all remaining transfers."""
        mock_ask.return_value = "s"
        pairs = [make_pair(Decimal("100")), make_pair(Decimal("200"))]

        confirmed, rejected = confirm_transfers(pairs)

        assert len(confirmed) == 0
        assert len(rejected) == 2
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `pytest tests/unit/test_transfer_confirmation.py -v`
- [x] Type checking: `ty check`
- [x] Linting: `ruff check`

#### Manual Verification:
- [x] Table displays correctly in terminal
- [x] All prompt choices work (y/n/a/s)

**Note**: Pause for manual confirmation before proceeding to next phase.

---

## Phase 4: Integrate into CLI Pipeline

### Overview
Wire up transfer detection and confirmation into the main CLI process command.

### Changes Required:

#### 1. Update CLI main.py
**File**: `src/budget_tracker/cli/main.py`
**Changes**: Add transfer detection after parsing, before categorization

Add imports at top:
```python
from budget_tracker.cli.transfer_confirmation import confirm_transfers
from budget_tracker.filters import TransferDetector
```

In the `process` function, after line 118 (`all_parsed_transactions.extend(parsed_transactions)`), add transfer detection:

```python
        # Step 1.5: Detect internal transfers
        console.print("\n[cyan]Detecting internal transfers...[/cyan]")
        detector = TransferDetector()
        transfer_pairs, non_transfer_transactions = detector.detect(all_parsed_transactions)

        # Confirm detected transfers with user
        confirmed_transfers, rejected_transfers = confirm_transfers(transfer_pairs)

        if confirmed_transfers:
            console.print(
                f"[green]✓[/green] {len(confirmed_transfers)} transfer(s) will be marked as Internal Transfer"
            )

        # Rebuild transaction list: rejected transfers go back to normal processing
        transactions_to_categorize = non_transfer_transactions.copy()
        for pair in rejected_transfers:
            transactions_to_categorize.append(pair.outgoing)
            transactions_to_categorize.append(pair.incoming)
```

Update the categorization loop (around line 126) to use `transactions_to_categorize`:

```python
        # Step 2: Categorize with LLM and create StandardTransactions
        console.print("\n[cyan]Categorizing transactions with local LLM...[/cyan]")
        categorizer = LLMCategorizer(_settings)
        currency_converter = CurrencyConverter()

        standardized: list[StandardTransaction] = []

        # First, add confirmed transfers (skip LLM categorization)
        for pair in confirmed_transfers:
            for parsed in [pair.outgoing, pair.incoming]:
                amount_dkk = currency_converter.convert(
                    amount=parsed.amount,
                    from_currency=parsed.currency,
                    to_currency="DKK",
                    transaction_date=parsed.date,
                )
                standardized.append(
                    StandardTransaction(
                        date=parsed.date,
                        category="Internal Transfer",
                        subcategory="Transfer",
                        amount=amount_dkk,
                        source=parsed.source,
                        description=parsed.description,
                        confidence=1.0,  # User confirmed
                    )
                )

        # Then categorize remaining transactions with LLM
        for parsed in transactions_to_categorize:
            # Categorize using description
            categorized = categorizer.categorize(parsed.description)

            # Convert currency to DKK
            amount_dkk = currency_converter.convert(
                amount=parsed.amount,
                from_currency=parsed.currency,
                to_currency="DKK",
                transaction_date=parsed.date,
            )

            # Create standardized transaction
            standardized.append(
                StandardTransaction(
                    date=parsed.date,
                    category=categorized.category,
                    subcategory=categorized.subcategory,
                    amount=amount_dkk,
                    source=parsed.source,
                    description=parsed.description,
                    confidence=categorized.confidence,
                )
            )
```

#### 2. Update integration tests
**File**: `tests/integration/test_end_to_end.py`
**Changes**: Add test for transfer detection in CLI

```python
@patch("budget_tracker.cli.main.is_ollama_running", return_value=True)
@patch("budget_tracker.cli.transfer_confirmation.confirm_transfers")
def test_process_with_transfers(
    mock_confirm_transfers,
    mock_ollama,
    cli_runner,
    temp_settings,
    sample_csv_file,
    mock_categorizer,
):
    """Test that transfer detection is called during processing."""
    # Mock confirm_transfers to return empty (no transfers)
    mock_confirm_transfers.return_value = ([], [])

    # Create a second CSV file simulating another bank
    second_csv = temp_settings.output_dir / "bank2.csv"
    second_csv.write_text(
        "Date,Amount,Description\n2024-01-15,100.00,Transfer from other\n"
    )

    # Create mappings for both banks
    # ... (setup bank mappings)

    # This test verifies the integration point exists
    # Full transfer detection is tested in unit tests
```

### Success Criteria:

#### Automated Verification:
- [ ] All tests pass: `pytest`
- [ ] Type checking: `ty check`
- [ ] Linting: `ruff check`
- [ ] Formatting: `ruff format --check`

#### Manual Verification:
- [ ] Process two bank CSVs with a matching transfer
- [ ] Transfer detection prompt appears
- [ ] Confirming marks transactions as "Internal Transfer"
- [ ] Rejecting sends transactions through LLM categorization
- [ ] Final export shows correct categories

---

## Testing Strategy

### Unit Tests:
- `test_transfer_detector.py` - Detection algorithm edge cases
- `test_transfer_confirmation.py` - UI confirmation logic with mocked input

### Integration Tests:
- Verify transfer detection integrates with CLI pipeline
- End-to-end test with two bank files containing transfers

### Manual Testing:
1. Create two CSV files with a matching transfer (e.g., -100 in bank A, +100 in bank B, same date)
2. Run: `budget-tracker process bank_a.csv bank_b.csv --banks bank_a bank_b`
3. Verify transfer detection prompt appears
4. Confirm the transfer and verify output shows "Internal Transfer" category
5. Test rejection flow - verify transaction goes through LLM
6. Test with `--sheets` flag to verify Google Sheets export works

## References
- Interactive confirmation pattern: `src/budget_tracker/cli/confirmation.py:10`
- Transaction model: `src/budget_tracker/models/transaction.py:13`
- CLI process command: `src/budget_tracker/cli/main.py:42`
- Categories config: `config/categories.yaml`
