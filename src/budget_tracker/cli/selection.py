import os
import sys

import questionary
from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.config.settings import Settings, get_settings

console = Console()


def is_interactive_terminal(settings: Settings) -> bool:
    """Check if the terminal supports interactive arrow-key selection.

    Returns False for:
    - Dumb terminals (TERM=dumb or TERM=unknown)
    - Non-TTY environments (piped input/output)
    - Explicity disabled via BUDGET_TRACKER_NO_INTERACTIVE env var
    """
    # Check for explicit disable
    if settings.no_interactive:
        return False

    # Check if stdin/stdout are TTYs
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    # Check for dumb terminal
    term = os.environ.get("TERM", "").lower()
    return term not in ("dumb", "unknown", "")

    return True


def select_option(
    message: str,
    choices: list[str],
    default: str | None = None,
    allow_back: bool = False,
) -> str | None:
    """Display an interactive selection menu.

    Uses questionary with arrow-key navigation on capable terminals,
    falls back to Rich Prompt on dumb terminals.

    Args:
        message: The prompt message to display
        choices: List of options to choose from
        default: Default selection (optional)
        allow_back: If True, adds "<- Go Back" option and enables Ctrl+B shortcut

    Returns:
        The selected option string
    """
    if allow_back:
        choices = [*choices, "<- Go Back"]

    if is_interactive_terminal(get_settings()):
        result = _questionary_select(message, choices, default)
    else:
        result = _rich_select(message, choices, default)

    if result == "<- Go Back":
        return None

    return result


def _questionary_select(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """Arrow-key selection using questionary."""
    result = questionary.select(
        message,
        choices=choices,
        default=default,
        use_shortcuts=True,  # Enable number keys alongside arrows
        use_arrow_keys=True,
        use_jk_keys=True,  # vim-style navigation
    ).ask()

    # Handle Ctrl+C (returns None)
    if result is None:
        raise KeyboardInterrupt

    return result


def _rich_select(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str:
    """Numbered selection fallback using Rich."""
    # Display numbered options
    console.print(f"\n[bold]{message}[/bold]")
    for i, choice in enumerate(choices, 1):
        console.print(f"  {i}. {choice}")

    # Build choices list (numbers as strings)
    num_choices = [str(i) for i in range(1, len(choices) + 1)]

    # Determine default number
    default_num = "1"
    if default and default in choices:
        default_num = str(choices.index(default) + 1)

    choice_num = Prompt.ask(
        "Select",
        choices=num_choices,
        default=default_num,
    )

    return choices[int(choice_num) - 1]
