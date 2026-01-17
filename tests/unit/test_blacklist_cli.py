from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_tracker.cli.blacklist import add_keyword, list_available_banks, remove_keyword
from budget_tracker.models.bank_mapping import BankMapping, ColumnMapping


@pytest.fixture
def sample_mapping() -> BankMapping:
    """Create a sample bank mapping for testing."""
    return BankMapping(
        bank_name="test_bank",
        column_mapping=ColumnMapping(
            date_column="Date",
            amount_column="Amount",
            description_columns=["Description"],
        ),
        blacklist_keywords=["MobilePay", "Visa"],
    )


@pytest.fixture
def empty_mapping() -> BankMapping:
    """Create a bank mapping with empty blacklist."""
    return BankMapping(
        bank_name="empty_bank",
        column_mapping=ColumnMapping(
            date_column="Date",
            amount_column="Amount",
            description_columns=["Description"],
        ),
        blacklist_keywords=[],
    )


def test_list_available_banks(tmp_path: Path) -> None:
    """Test listing available bank configurations."""
    (tmp_path / "danske_bank.yaml").touch()
    (tmp_path / "nordea.yaml").touch()

    banks = list_available_banks(tmp_path)

    assert banks == ["danske_bank", "nordea"]


def test_list_available_banks_empty_dir(tmp_path: Path) -> None:
    """Test listing banks when directory is empty."""
    banks = list_available_banks(tmp_path)
    assert banks == []


def test_list_available_banks_nonexistent_dir() -> None:
    """Test listing banks when directory does not exist."""
    banks = list_available_banks(Path("/non/existent/path"))
    assert banks == []


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_keyword(
    mock_prompt: MagicMock, mock_save: MagicMock, sample_mapping: BankMapping, tmp_path: Path
) -> None:
    """Test adding a keyword to the blacklist."""
    mock_prompt.return_value = "NewKeyword"

    add_keyword(sample_mapping, tmp_path)

    assert "NewKeyword" in sample_mapping.blacklist_keywords
    mock_save.assert_called_once_with(sample_mapping, tmp_path)


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_duplicate_keyword(
    mock_prompt: MagicMock, mock_save: MagicMock, sample_mapping: BankMapping, tmp_path: Path
) -> None:
    """Test adding a duplicate keyword to the blacklist shows warning"""
    mock_prompt.return_value = "MobilePay"

    add_keyword(sample_mapping, tmp_path)

    # Should not save since keyword already exists
    mock_save.assert_not_called()
    # Should still have only one instance
    assert sample_mapping.blacklist_keywords.count("MobilePay") == 1


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_add_empty_keyword(
    mock_prompt: MagicMock, mock_save: MagicMock, sample_mapping: BankMapping, tmp_path: Path
) -> None:
    """Test adding empty keyword is rejected."""
    mock_prompt.return_value = "   "

    add_keyword(sample_mapping, tmp_path)

    mock_save.assert_not_called()


@patch("budget_tracker.cli.blacklist.save_mapping")
@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_remove_keyword(
    mock_prompt: MagicMock, mock_save: MagicMock, sample_mapping: BankMapping, tmp_path: Path
) -> None:
    """Test removing a keyword from the blacklist."""
    mock_prompt.return_value = "1"  # Remove first keyword (MobilePay)

    remove_keyword(sample_mapping, tmp_path)

    assert "MobilePay" not in sample_mapping.blacklist_keywords
    assert "Visa" in sample_mapping.blacklist_keywords
    mock_save.assert_called_once()


@patch("budget_tracker.cli.blacklist.Prompt.ask")
def test_remove_keyword_cancelled(
    mock_prompt: MagicMock, sample_mapping: BankMapping, tmp_path: Path
) -> None:
    """Test cancelling keyword removal."""
    mock_prompt.return_value = ""  # Press Enter to cancel

    original_keywords = sample_mapping.blacklist_keywords.copy()
    remove_keyword(sample_mapping, tmp_path)

    assert sample_mapping.blacklist_keywords == original_keywords


def test_remove_keyword_empty_blacklist(empty_mapping: BankMapping, tmp_path: Path) -> None:
    """Test removing keyword from empty blacklist."""
    remove_keyword(empty_mapping, tmp_path)  # Should handle gracefully without error
