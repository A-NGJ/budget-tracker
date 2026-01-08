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
            pair.outgoing.description[:40] + "..."
            if len(pair.outgoing.description) > 40
            else pair.outgoing.description,
        )
        table.add_row(
            "IN",
            str(pair.incoming.date),
            f"{pair.incoming.amount:.2f} {pair.incoming.currency}",
            pair.incoming.source,
            pair.incoming.description[:40] + "..."
            if len(pair.incoming.description) > 40
            else pair.incoming.description,
        )

        console.print(table)

        choice = Prompt.ask(
            "Mark as internal transfer?",
            choices=["y", "n", "a", "s"],
            default="y",
        )

        match choice:
            case "y":
                confirmed.append(pair)
                console.print("[green]Marked as internal transfer[/green]")
            case "n":
                rejected.append(pair)
                console.print("[yellow]Will categorize normally[/yellow]")
            case "a":
                # Accept all remaining
                confirmed.append(pair)
                confirmed.extend(pairs[i:])
                console.print(f"[green]Marked {len(pairs) - i + 1} transfer(s) as internal[/green]")
                break
            case _:  # skip all
                rejected.append(pair)
                rejected.extend(pairs[i:])
                console.print(f"[yellow]Skipping {len(pairs) - i + 1} pair(s)[/yellow]")
                break

    return confirmed, rejected
