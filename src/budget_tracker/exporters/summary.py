from collections import defaultdict
from decimal import Decimal

from rich.console import Console
from rich.table import Table

from budget_tracker.models.transaction import StandardTransaction

console = Console()


def print_summary(transactions: list[StandardTransaction]) -> None:
    """Print summary statistics of processed transactions"""
    total_transactions = len(transactions)
    total_expenses = sum(t.amount for t in transactions if t.amount < 0)
    total_income = sum(t.amount for t in transactions if t.amount > 0)

    # By category
    by_category: defaultdict[str, Decimal] = defaultdict(Decimal)
    for t in transactions:
        if t.amount < 0:  # Only expenses
            by_category[t.category] += abs(t.amount)

    # By source
    by_source: defaultdict[str, int] = defaultdict(int)
    for t in transactions:
        by_source[t.source] += 1

    console.print("\n[bold]Transaction Summary[/bold]")
    console.print(f"Total transactions: {total_transactions}")
    console.print(f"Total expenses: {total_expenses:.2f} DKK")
    console.print(f"Total income: {total_income:.2f} DKK")

    # Category breakdown
    if by_category:
        console.print("\n[bold]Expenses by Category:[/bold]")
        table = Table(show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Amount (DKK)", justify="right", style="magenta")

        for category, amount in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            table.add_row(category, f"{amount:.2f}")

        console.print(table)

    # Source breakdown
    console.print("\n[bold]Transactions by Source:[/bold]")
    for source, count in sorted(by_source.items()):
        console.print(f"  {source}: {count} transactions")
