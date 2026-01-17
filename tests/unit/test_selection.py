import os
from unittest.mock import MagicMock, patch

import pytest

from budget_tracker.cli.selection import _rich_select, is_interactive_terminal, select_option
from budget_tracker.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(no_interactive=False)


class TestIsInteractiveTerminal:
    """Tests for terminal detection."""

    def test_returns_false_when_env_var_set(self, settings: Settings) -> None:
        """Explicit disable via environment variable."""
        settings.no_interactive = True
        with patch.dict(os.environ, {"BUDGET_TRACKER_NO_INTERACTIVE": "1"}):
            assert is_interactive_terminal(settings) is False

    def test_returns_false_when_stdin_not_tty(self, settings: Settings) -> None:
        """Non-TTY stdin (e.g., piped input)."""
        with patch("sys.stdin.isatty", return_value=False):
            assert is_interactive_terminal(settings) is False

    def test_returns_false_when_stdout_not_tty(self, settings: Settings) -> None:
        """Non-TTY stdout (e.g., piped output)."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=False),
        ):
            assert is_interactive_terminal(settings) is False

    def test_returns_false_for_dumb_terminal(self, settings: Settings) -> None:
        """Dumb terminal should use fallback."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch.dict(os.environ, {"TERM": "dumb"}, clear=False),
        ):
            assert is_interactive_terminal(settings) is False

    def test_returns_false_for_unknown_terminal(self, settings: Settings) -> None:
        """Unknown terminal should use fallback."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch.dict(os.environ, {"TERM": "unknown"}, clear=False),
        ):
            assert is_interactive_terminal(settings) is False

    def test_returns_true_for_xterm(self, settings: Settings) -> None:
        """Standard xterm should be interactive."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=False),
        ):
            assert is_interactive_terminal(settings) is True


class TestSelectOption:
    """Tests for select_option function."""

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=False)
    @patch("budget_tracker.cli.selection._rich_select")
    def test_uses_rich_fallback_on_dumb_terminal(
        self,
        mock_rich: MagicMock,
        mock_is_interactive: MagicMock,  # noqa: ARG002
    ) -> None:
        """Should use Rich when terminal is not interactive."""
        mock_rich.return_value = "Option 1"

        result = select_option("Choose:", ["Option 1", "Option 2"])

        mock_rich.assert_called_once_with("Choose:", ["Option 1", "Option 2"], None)
        assert result == "Option 1"

    @patch("budget_tracker.cli.selection.is_interactive_terminal", return_value=True)
    @patch("budget_tracker.cli.selection._questionary_select")
    def test_uses_questionary_on_interactive_terminal(
        self,
        mock_quest: MagicMock,
        mock_is_interactive: MagicMock,  # noqa: ARG002
    ) -> None:
        """Should use questionary when terminal is interactive."""
        mock_quest.return_value = "Option 2"

        result = select_option("Choose:", ["Option 1", "Option 2"], default="Option 2")

        mock_quest.assert_called_once_with("Choose:", ["Option 1", "Option 2"], "Option 2")
        assert result == "Option 2"


class TestRichSelect:
    """Tests for Rich fallback selection."""

    @patch("budget_tracker.cli.selection.Prompt.ask")
    def test_returns_selected_choice(self, mock_prompt: MagicMock) -> None:
        """Should return the choice corresponding to selected number."""
        mock_prompt.return_value = "2"

        result = _rich_select("Pick one:", ["Apple", "Banana", "Cherry"])

        assert result == "Banana"

    @patch("budget_tracker.cli.selection.Prompt.ask")
    def test_passes_default_as_number(self, mock_prompt: MagicMock) -> None:
        """Should convert default choice to its number."""
        mock_prompt.return_value = "2"

        _rich_select("Pick one:", ["Apple", "Banana", "Cherry"], default="Banana")

        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args[1]
        assert call_kwargs["default"] == "2"  # Banana is index 1, so number 2
