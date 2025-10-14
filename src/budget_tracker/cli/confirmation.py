from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.config.settings import Settings
from budget_tracker.models.transaction import StandardTransaction

console = Console()


def confirm_uncertain_categories(
    settings: Settings,
    transactions: list[StandardTransaction],
) -> list[StandardTransaction]:
    """
    Show transactions with low confidence and ask for user confirmation.

    Args:
        transactions: List of categorized transactions

    Returns:
        Updated list with user-confirmed categories
    """
    uncertain = [t for t in transactions if t.confidence < 0.6]

    if not uncertain:
        return transactions

    console.print(f"\n[yellow]⚠[/yellow] Found {len(uncertain)} transactions needing review:")

    categories = settings.load_categories()
    category_names = [c["name"] for c in categories["categories"]]

    for transaction in uncertain:
        console.print(f"\n[bold]Transaction:[/bold] {transaction.description}")
        console.print(f"[dim]Amount: {transaction.amount} DKK[/dim]")
        console.print(
            f"[dim]Suggested: {transaction.category} "
            f"(confidence: {transaction.confidence:.0%})[/dim]"
        )

        choice = Prompt.ask("Accept suggestion?", choices=["y", "n", "s"], default="y")

        if choice == "y":
            continue  # Keep suggested category
        elif choice == "n":
            # Let user pick category
            console.print("\nAvailable categories:")
            for i, cat in enumerate(category_names, 1):
                console.print(f"  {i}. {cat}")

            cat_choice = Prompt.ask(
                "Select category number",
                choices=[str(i) for i in range(1, len(category_names) + 1)],
            )
            new_category = category_names[int(cat_choice) - 1]
            transaction.category = new_category
            transaction.confidence = 1.0  # User-confirmed
        else:  # skip
            transaction.category = "Other"
            transaction.subcategory = "Uncategorized"

    return transactions
