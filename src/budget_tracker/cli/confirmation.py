from rich.console import Console
from rich.prompt import Prompt

from budget_tracker.cli.selection import select_option
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
    subcategories = [c.get("subcategories", []) for c in categories["categories"]]

    # Cache for confirmed descriptions: {description: (category, subcategory)}
    confirmed_cache: dict[str, tuple[str, str | None]] = {}

    for transaction in uncertain:
        # Skip transactions without description
        if not transaction.description:
            continue

        # Check if we've already confirmed this description
        if transaction.description in confirmed_cache:
            cached_category, cached_subcategory = confirmed_cache[transaction.description]
            transaction.category = cached_category
            transaction.subcategory = cached_subcategory
            transaction.confidence = 1.0
            console.print(
                f"\n[dim]Reusing category for: {transaction.description} → {cached_category}[/dim]"
            )
            continue
        console.print(f"\n[bold]Transaction:[/bold] {transaction.description}")
        console.print(f"[dim]Amount: {transaction.amount} DKK[/dim]")
        console.print(
            f"[dim]Suggested: {transaction.category} "
            f"(confidence: {transaction.confidence:.0%})[/dim]"
        )

        choice = Prompt.ask("Accept suggestion?", choices=["y", "n", "s"], default="y")

        if choice == "y":
            # Cache the accepted suggestion
            confirmed_cache[transaction.description] = (
                transaction.category,
                transaction.subcategory,
            )
            transaction.confidence = 1.0
        elif choice == "n":
            # Let user pick category
            new_category = select_option("\nSelect category", category_names)
            if new_category is None:
                console.print("  [red]Application error.[/red]")
                raise KeyboardInterrupt

            cat_index = category_names.index(new_category)
            subcat_list = subcategories[cat_index]
            if subcat_list:
                subcat_choices = [*subcat_list, "(Skip)"]
                subcat_selection = select_option(
                    f"Select subcategory for {new_category}",
                    subcat_choices,
                    default="(Skip)",
                )
                new_subcategory = None if subcat_selection == "(Skip)" else subcat_selection
            else:
                console.print(f"  (No subcategories available for {new_category})")
                new_subcategory = None

            transaction.category = new_category
            transaction.subcategory = new_subcategory  # Clear subcategory when changing category
            transaction.confidence = 1.0  # User-confirmed
            # Cache the user's choice
            confirmed_cache[transaction.description] = (new_category, new_subcategory)
        else:  # skip
            transaction.category = "Other"
            transaction.subcategory = "Uncategorized"
            # Cache the skip decision
            confirmed_cache[transaction.description] = ("Other", "Uncategorized")

    return transactions
