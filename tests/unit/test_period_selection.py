from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
import typer

from budget_tracker.analytics.models import AnalyticsPeriod
from budget_tracker.cli.period_selection import (
    _build_presets,
    _count_in_range,
    parse_period_flags,
    resolve_period,
    select_period_interactive,
)
from budget_tracker.models.transaction import StandardTransaction


def make_tx(date_str: str = "2024-06-15") -> StandardTransaction:
    """Create a minimal StandardTransaction for testing (bypasses validators)."""
    return StandardTransaction.model_construct(
        date=date.fromisoformat(date_str),
        category="Food & Drinks",
        subcategory="Groceries",
        amount=Decimal("-50"),
        source="Test Bank",
    )


# ---------------------------------------------------------------------------
# parse_period_flags
# ---------------------------------------------------------------------------


class TestParsePeriodFlags:
    def test_both_dates_provided(self) -> None:
        result = parse_period_flags("2024-01-01", "2024-12-31")
        assert result.from_date == date(2024, 1, 1)
        assert result.to_date == date(2024, 12, 31)
        assert "Jan 2024" in result.label
        assert "Dec 2024" in result.label

    def test_only_from_date(self) -> None:
        result = parse_period_flags("2024-06-01", None)
        assert result.from_date == date(2024, 6, 1)
        assert result.to_date is None
        assert "Jun 2024" in result.label
        assert "..." in result.label

    def test_only_to_date(self) -> None:
        result = parse_period_flags(None, "2024-06-30")
        assert result.from_date is None
        assert result.to_date == date(2024, 6, 30)
        assert "..." in result.label
        assert "Jun 2024" in result.label

    def test_both_none_returns_all_time(self) -> None:
        result = parse_period_flags(None, None)
        assert result.from_date is None
        assert result.to_date is None
        assert result.label == "All Time"

    def test_invalid_from_date_raises(self) -> None:
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            parse_period_flags("not-a-date", None)

    def test_invalid_to_date_raises(self) -> None:
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            parse_period_flags(None, "2024/01/01")


# ---------------------------------------------------------------------------
# _count_in_range
# ---------------------------------------------------------------------------


class TestCountInRange:
    def test_both_bounds(self) -> None:
        txs = [make_tx("2024-01-01"), make_tx("2024-06-15"), make_tx("2024-12-31")]
        assert _count_in_range(txs, date(2024, 3, 1), date(2024, 9, 1)) == 1

    def test_open_from(self) -> None:
        txs = [make_tx("2024-01-01"), make_tx("2024-06-15")]
        assert _count_in_range(txs, None, date(2024, 3, 1)) == 1

    def test_open_to(self) -> None:
        txs = [make_tx("2024-01-01"), make_tx("2024-06-15")]
        assert _count_in_range(txs, date(2024, 3, 1), None) == 1

    def test_both_none_counts_all(self) -> None:
        txs = [make_tx("2024-01-01"), make_tx("2024-06-15"), make_tx("2024-12-31")]
        assert _count_in_range(txs, None, None) == 3

    def test_empty_list(self) -> None:
        assert _count_in_range([], date(2024, 1, 1), date(2024, 12, 31)) == 0

    def test_boundary_inclusive(self) -> None:
        txs = [make_tx("2024-06-15")]
        assert _count_in_range(txs, date(2024, 6, 15), date(2024, 6, 15)) == 1


# ---------------------------------------------------------------------------
# _build_presets
# ---------------------------------------------------------------------------


class TestBuildPresets:
    def test_empty_transactions(self) -> None:
        presets = _build_presets([])
        assert len(presets) == 5
        assert "0 transactions" in presets[0][0]
        # Custom range is last
        assert "Custom range" in presets[-1][0]

    def test_all_time_shows_date_range(self) -> None:
        txs = [make_tx("2024-01-15"), make_tx("2024-09-20")]
        presets = _build_presets(txs)
        all_time_label = presets[0][0]
        assert "2 transactions" in all_time_label
        assert "Jan 2024" in all_time_label
        assert "Sep 2024" in all_time_label

    def test_all_time_has_none_dates(self) -> None:
        txs = [make_tx("2024-01-15")]
        presets = _build_presets(txs)
        _, from_date, to_date = presets[0]
        assert from_date is None
        assert to_date is None

    def test_preset_count_is_five(self) -> None:
        txs = [make_tx("2024-06-15")]
        presets = _build_presets(txs)
        assert len(presets) == 5  # all time, last month, last 3 months, last year, custom

    def test_last_month_counts_correctly(self) -> None:
        today = datetime.now(tz=UTC).date()
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        mid_prev_month = last_of_prev_month.replace(day=15)

        txs = [make_tx(mid_prev_month.isoformat()), make_tx("2020-01-01")]
        presets = _build_presets(txs)
        last_month_label = presets[1][0]
        assert "1 transactions" in last_month_label


# ---------------------------------------------------------------------------
# select_period_interactive
# ---------------------------------------------------------------------------


class TestSelectPeriodInteractive:
    @patch("budget_tracker.cli.period_selection.select_option")
    def test_selecting_all_time_preset(self, mock_select: object) -> None:
        txs = [make_tx("2024-01-15"), make_tx("2024-09-20")]
        presets = _build_presets(txs)
        mock_select.return_value = presets[0][0]  # type: ignore[union-attr]

        result = select_period_interactive(txs)
        assert result.from_date is None
        assert result.to_date is None
        assert result.label == "All Time"

    @patch("budget_tracker.cli.period_selection._prompt_custom_range")
    @patch("budget_tracker.cli.period_selection.select_option")
    def test_selecting_custom_range_delegates(
        self, mock_select: object, mock_custom: object
    ) -> None:
        txs = [make_tx("2024-01-15")]
        presets = _build_presets(txs)
        mock_select.return_value = presets[-1][0]  # "Custom range..."  # type: ignore[union-attr]
        expected = AnalyticsPeriod(
            from_date=date(2024, 1, 1), to_date=date(2024, 6, 30), label="Jan 2024 - Jun 2024"
        )
        mock_custom.return_value = expected  # type: ignore[union-attr]

        result = select_period_interactive(txs)
        assert result == expected
        mock_custom.assert_called_once()  # type: ignore[union-attr]

    @patch("budget_tracker.cli.period_selection.select_option")
    def test_selecting_last_year_preset(self, mock_select: object) -> None:
        txs = [make_tx("2024-06-15")]
        presets = _build_presets(txs)
        mock_select.return_value = presets[3][0]  # last year  # type: ignore[union-attr]

        result = select_period_interactive(txs)
        prev_year = datetime.now(tz=UTC).date().year - 1
        assert result.from_date == date(prev_year, 1, 1)
        assert result.to_date == date(prev_year, 12, 31)


# ---------------------------------------------------------------------------
# resolve_period
# ---------------------------------------------------------------------------


class TestResolvePeriod:
    def test_cli_flags_take_priority(self) -> None:
        txs = [make_tx("2024-06-15")]
        result = resolve_period("2024-01-01", "2024-12-31", txs)
        assert result.from_date == date(2024, 1, 1)
        assert result.to_date == date(2024, 12, 31)

    def test_no_interactive_defaults_to_all_time(self) -> None:
        txs = [make_tx("2024-06-15")]
        result = resolve_period(None, None, txs, no_interactive=True)
        assert result.from_date is None
        assert result.to_date is None
        assert result.label == "All Time"

    @patch("budget_tracker.cli.period_selection.select_period_interactive")
    def test_no_flags_calls_interactive(self, mock_interactive: object) -> None:
        expected = AnalyticsPeriod(from_date=None, to_date=None, label="All Time")
        mock_interactive.return_value = expected  # type: ignore[union-attr]
        txs = [make_tx("2024-06-15")]

        result = resolve_period(None, None, txs, no_interactive=False)
        assert result == expected
        mock_interactive.assert_called_once_with(txs)  # type: ignore[union-attr]

    def test_only_from_flag_skips_interactive(self) -> None:
        txs = [make_tx("2024-06-15")]
        result = resolve_period("2024-01-01", None, txs)
        assert result.from_date == date(2024, 1, 1)
        assert result.to_date is None
