"""Detect internal transfers between bank accounts."""

from collections import defaultdict

from pydantic import BaseModel

from budget_tracker.parsers.csv_parser import ParsedTransaction


class TransferPair(BaseModel):
    """A matched pair of transactions representing an internal transfer."""

    outgoing: ParsedTransaction  # Negative amount (money leaving)
    incoming: ParsedTransaction  # Positive amount (money arriving)

    @property
    def amount(self) -> float:
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
        - Two transactions ahve the same absolute amount
        - One is positive, one is negative
        - They occur on the same date
        - They come from different bank sources

        Args:
            transactions: List of parsed transactions from multiple banks

        Returns:
            Tuple of (detected transfer pairs, remaining transactions)
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
