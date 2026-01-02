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
            console.print("\nAvailable categories:")
            for i, cat in enumerate(category_names, 1):
                console.print(f"  {i}. {cat}")

            cat_choice = Prompt.ask(
                "Select category number",
                choices=[str(i) for i in range(1, len(category_names) + 1)],
            )

            console.print(f"\nAvailable subcategories for {category_names[int(cat_choice) - 1]}:")
            subcat_list = subcategories[int(cat_choice) - 1]
            if subcat_list:
                for i, subcat in enumerate(subcat_list, 1):
                    console.print(f"  {i}. {subcat}")
                subcat_choice = Prompt.ask(
                    "Select subcategory number (or press Enter to skip)",
                    choices=[str(i) for i in range(1, len(subcat_list) + 1)] + [""],
                    default="",
                )
                new_subcategory = subcat_list[int(subcat_choice) - 1] if subcat_choice else None
            else:
                console.print("  (No subcategories available)")
                new_subcategory = None
            new_category = category_names[int(cat_choice) - 1]
            transaction.category = new_category
            transaction.subcategory = new_subcategory  # Clear subcategory when changing category
            transaction.confidence = 1.0  # User-confirmed
            # Cache the user's choice
            confirmed_cache[transaction.description] = (new_category, None)
        else:  # skip
            transaction.category = "Other"
            transaction.subcategory = "Uncategorized"
            # Cache the skip decision
            confirmed_cache[transaction.description] = ("Other", "Uncategorized")

    return transactions
