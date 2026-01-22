from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from budget_tracker.cli.mapping import (
    MappingState,
    MappingStep,
    StepResult,
    _build_mapping,
    _step_date_column,
    interactive_column_mapping,
    load_mapping,
    save_mapping,
)
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


@pytest.fixture
def sample_columns() -> list[str]:
    """Standard column list for testing."""
    return ["Date", "Amount", "Description", "Category", "Currency"]


@pytest.fixture
def complete_state() -> MappingState:
    """Fully populated MappingState for testing."""
    return MappingState(
        bank_name="Test Bank",
        date_col="Date",
        amount_col="Amount",
        desc_cols=["Description"],
        currency_col=None,
        default_currency="DKK",
        date_format="%Y-%m-%d",
        decimal_separator=".",
    )


class TestBankMappingYAML:
    def test_save_mapping_creates_yaml_file(self, tmp_path: Path) -> None:
        """Test that save_mapping creates a YAML file."""
        banks_dir = tmp_path / "banks"
        mapping = BankMapping(
            bank_name="test_bank",
            column_mapping=ColumnMapping(
                date_column="Date",
                amount_column="Amount",
                description_columns=["Desc"],
            ),
        )

        save_mapping(mapping, banks_dir)

        yaml_file = banks_dir / "test_bank.yaml"
        assert yaml_file.exists()

        with yaml_file.open() as f:
            data = yaml.safe_load(f)
        assert data["bank_name"] == "test_bank"

    def test_load_mapping_reads_yaml_file(self, tmp_path: Path) -> None:
        """Test that load_mapping reads YAML file."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        yaml_file = banks_dir / "test_bank.yaml"
        yaml_file.write_text(
            yaml.safe_dump(
                {
                    "bank_name": "test_bank",
                    "column_mapping": {
                        "date_column": "Date",
                        "amount_column": "Amount",
                        "description_columns": ["Desc"],
                    },
                }
            )
        )

        mapping = load_mapping("test_bank", banks_dir)

        assert mapping is not None
        assert mapping.bank_name == "test_bank"

    def test_load_mapping_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Test that load_mapping returns None for missing bank."""
        banks_dir = tmp_path / "banks"
        banks_dir.mkdir()

        mapping = load_mapping("non_existent_bank", banks_dir)

        assert mapping is None


class TestMappingState:
    """Test MappingState dataclass initialization and defaults"""

    def test_initializes_with_none_values(self) -> None:
        """Verify MappingState fields initialize to expected defaults."""
        state = MappingState()

        assert state.bank_name is None
        assert state.date_col is None
        assert state.amount_col is None
        assert state.desc_cols == []
        assert state.currency_col is None
        assert state.default_currency == "DKK"
        assert state.has_currency_column is False
        assert state.date_format is None
        assert state.decimal_separator is None

    def test_desc_cols_uses_independent_list(self) -> None:
        """Verify each MappingState instance has its own desc_cols list."""
        state1 = MappingState()
        state2 = MappingState()

        state1.desc_cols.append("Description")

        assert state2.desc_cols == []  # Should not be affected

    def test_accepts_initial_values(self) -> None:
        """Verify MappingState accepts initial values."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            default_currency="EUR",
        )

        assert state.bank_name == "Test Bank"
        assert state.date_col == "Date"
        assert state.default_currency == "EUR"


class TestStepDateColumn:
    """Tests for _step_date_column."""

    @patch("budget_tracker.cli.mapping.select_option")
    def test_returns_back_when_none_selected(self, mock_select: MagicMock) -> None:
        """Verify BACK is returned when select_option returns None."""
        mock_select.return_value = None
        state = MappingState()

        result = _step_date_column(state, ["Date", "Amount"], allow_back=True)

        assert result == StepResult.BACK
        assert state.date_col is None  # State unchanged

    @patch("budget_tracker.cli.mapping.select_option")
    def test_stores_selection_and_returns_next(self, mock_select: MagicMock) -> None:
        """Verify selection is stored and NEXT is returned."""
        mock_select.return_value = "Date"
        state = MappingState()

        result = _step_date_column(state, ["Date", "Amount"], allow_back=True)

        assert result == StepResult.NEXT
        assert state.date_col == "Date"

    @patch("budget_tracker.cli.mapping.select_option")
    def test_passes_previous_selection_as_default(self, mock_select: MagicMock) -> None:
        """Verify previous selection is passed as default when going back."""
        mock_select.return_value = "Date"
        state = MappingState(date_col="Amount")  # Previous selection

        _step_date_column(state, ["Date", "Amount"], allow_back=True)

        # Verify default was passed
        call_kwargs = mock_select.call_args
        assert call_kwargs[1]["default"] == "Amount"


class TestInteractiveColumnMappingNavigation:
    """Tests for step-based navigation in interactive_column_mapping."""

    @pytest.fixture
    def sample_columns(self) -> list[str]:
        return ["Date", "Amount", "Description", "Currency"]

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping._build_mapping")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_forward_navigation_increments_step(
        self,
        mock_print: MagicMock,  # noqa: ARG002
        mock_build: MagicMock,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify NEXT result moves to next step."""
        mock_execute.side_effect = [
            StepResult.NEXT,
            StepResult.NEXT,
            StepResult.DONE,
        ]
        mock_build.return_value = MagicMock()

        interactive_column_mapping(sample_columns)

        # Should have called execute 3 times for steps 0, 1, 2
        assert mock_execute.call_count == 3

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_back_navigation_decrements_step(
        self,
        mock_print: MagicMock,  # noqa: ARG002,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify BACK result moves to previous step."""
        mock_execute.side_effect = [
            StepResult.NEXT,  # Step 0 → 1
            StepResult.NEXT,  # Step 1 → 2
            StepResult.BACK,  # Step 2 → 1
            StepResult.CANCEL,  # Exit
        ]

        interactive_column_mapping(sample_columns)

        # Step 1 should be called twice (forward and after back)
        assert mock_execute.call_count == 4

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_back_from_first_step_stays_at_first(
        self,
        mock_print: MagicMock,  # noqa: ARG002,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify BACK from step 0 stays at step 0."""
        mock_execute.side_effect = [
            StepResult.BACK,  # Can't go back, stays at 0
            StepResult.CANCEL,  # Exit
        ]

        interactive_column_mapping(sample_columns)

        # First step should be called twice
        assert mock_execute.call_count == 2
        # Both calls should be for step index 0 (MappingStep.BANK_NAME)
        first_call_step = mock_execute.call_args_list[0][0][0]
        second_call_step = mock_execute.call_args_list[1][0][0]
        assert first_call_step == MappingStep.BANK_NAME
        assert second_call_step == MappingStep.BANK_NAME

    @patch("budget_tracker.cli.mapping._execute_step")
    @patch("budget_tracker.cli.mapping.console.print")
    def test_cancel_returns_none(
        self,
        mock_print: MagicMock,  # noqa: ARG002,
        mock_execute: MagicMock,
        sample_columns: list[str],
    ) -> None:
        """Verify CANCEL result returns None from flow."""
        mock_execute.return_value = StepResult.CANCEL

        result = interactive_column_mapping(sample_columns)

        assert result is None


class TestBuildMapping:
    """Tests for _build_mapping validation."""

    def test_raises_on_missing_bank_name(self) -> None:
        """Verify ValueError raised when bank_name is None."""
        state = MappingState(
            date_col="Date",
            amount_col="Amount",
            desc_cols=["Description"],
            date_format="%Y-%m-%d",
            decimal_separator=".",
        )

        with pytest.raises(ValueError, match="bank_name is required"):
            _build_mapping(state)

    def test_raises_on_empty_desc_cols(self) -> None:
        """Verify ValueError raised when desc_cols is empty."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            amount_col="Amount",
            desc_cols=[],  # Empty!
            date_format="%Y-%m-%d",
            decimal_separator=".",
        )

        with pytest.raises(ValueError, match="desc_cols is required"):
            _build_mapping(state)

    def test_builds_valid_mapping(self) -> None:
        """Verify valid state produces correct BankMapping."""
        state = MappingState(
            bank_name="Test Bank",
            date_col="Date",
            amount_col="Amount",
            desc_cols=["Description", "Category"],
            currency_col="Currency",
            default_currency="EUR",
            date_format="%d-%m-%Y",
            decimal_separator=",",
        )

        result = _build_mapping(state)

        assert result.bank_name == "Test Bank"
        assert result.column_mapping.date_column == "Date"
        assert result.column_mapping.description_columns == ["Description", "Category"]
        assert result.default_currency == "EUR"
        assert result.decimal_separator == ","
