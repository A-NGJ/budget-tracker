from rich.console import Console

from budget_tracker.cli.selection import select_option
from budget_tracker.config.settings import Settings
from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.parsers.csv_parser import ParsedTransaction

console = Console()


def categorize_transactions(
    settings: Settings,
    transactions: list[ParsedTransaction],
    currency_converter: CurrencyConverter,
) -> list[StandardTransaction]:
    """
    Prompt user to categorize each transaction via interactive selection.
    Caches choices by description so duplicates are auto-resolved.
    """
    categories = settings.load_categories()
    category_names = [c["name"] for c in categories["categories"]]
    subcategories = [c.get("subcategories", []) for c in categories["categories"]]

    # Cache: {description: (category, subcategory)}
    confirmed_cache: dict[str, tuple[str, str | None]] = {}
    standardized: list[StandardTransaction] = []

    for parsed in transactions:
        # Convert currency
        amount_dkk = currency_converter.convert(
            amount=parsed.amount,
            from_currency=parsed.currency,
            to_currency="DKK",
            transaction_date=parsed.date,
        )

        # Check cache
        if parsed.description in confirmed_cache:
            cat, subcat = confirmed_cache[parsed.description]
            console.print(f"\n[dim]Reusing category for: {parsed.description} → {cat}[/dim]")
            standardized.append(
                StandardTransaction(
                    date=parsed.date,
                    category=cat,
                    subcategory=subcat,
                    amount=amount_dkk,
                    source=parsed.source,
                    description=parsed.description,
                )
            )
            continue

        # Show transaction info
        console.print(f"\n[bold]Transaction:[/bold] {parsed.description}")
        console.print(f"[dim]Amount: {amount_dkk} DKK | Date: {parsed.date}[/dim]")

        # User selects category
        new_category = select_option("\nSelect category", category_names)
        if new_category is None:
            console.print("  [red]Application error.[/red]")
            raise KeyboardInterrupt

        # Subcategory selection
        cat_index = category_names.index(new_category)
        subcat_list = subcategories[cat_index]
        new_subcategory = None
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

        # Cache and create transaction
        confirmed_cache[parsed.description] = (new_category, new_subcategory)
        standardized.append(
            StandardTransaction(
                date=parsed.date,
                category=new_category,
                subcategory=new_subcategory,
                amount=amount_dkk,
                source=parsed.source,
                description=parsed.description,
            )
        )

    return standardized
