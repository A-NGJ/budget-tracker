import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from budget_tracker.categorizer.llm_categorizer import LLMCategorizer
from budget_tracker.cli.confirmation import confirm_uncertain_categories
from budget_tracker.cli.mapping import interactive_column_mapping, load_mapping, save_mapping
from budget_tracker.config.settings import Settings, get_settings
from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.exporters.summary import print_summary
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.parsers.csv_parser import CSVParser, ParsedTransaction
from budget_tracker.utils.ollama import is_ollama_running

console = Console()


def create_app(settings: Settings | None = None) -> typer.Typer:
    """Create the Typer app with injected settings.

    Args:
        settings: Settings instance to use. If None, uses get_settings().

    Returns:
        Configured Typer app.
    """
    app = typer.Typer(help="Bank Statement Normalizer - Standardize and categorize your transactions")
    _settings = settings or get_settings()

    @app.callback()
    def main_callback(ctx: typer.Context) -> None:
        """Initialize the app with settings."""
        ctx.ensure_object(dict)
        ctx.obj["settings"] = _settings

    @app.command()
    def process(
        ctx: typer.Context,
        files: Annotated[list[Path], typer.Argument(help="CSV files to process")],
        output: Annotated[
            Path | None, typer.Option("--output", "-o", help="Output CSV file path")
        ] = None,
    ) -> None:
        """
        Process bank statement CSV files and generate standardized output.

        Examples:
            budget-tracker process bank1.csv
            budget-tracker process bank1.csv bank2.csv --output results.csv
        """
        settings: Settings = ctx.obj["settings"]

        console.print("[bold]Budget Tracker - Bank Statement Normalizer[/bold]\n")

        if not is_ollama_running():
            console.print("[red]✗[/red] Ollama server is not running. Please start it and try again.")
            raise typer.Exit(1)

        # Ensure directories exist
        settings.ensure_directories()

        # Validate input files
        for file in files:
            if not file.exists():
                console.print(f"[red]✗[/red] File not found: {file}")
                raise typer.Exit(1)

        console.print(f"Processing {len(files)} file(s)...")

        # Step 1: Parse CSV files with column mapping
        parser = CSVParser()
        all_parsed_transactions: list[ParsedTransaction] = []

        for file in files:
            console.print(f"\n[cyan]Processing:[/cyan] {file.name}")

            # Try to load saved mapping
            mapping = load_mapping(file.stem, settings.mappings_file)

            if not mapping:
                # Interactive column mapping
                _, columns = parser.parse_file(file)
                console.print(f"Detected {len(columns)} columns: {', '.join(columns)}")

                mapping = interactive_column_mapping(file, columns)
                if not mapping:
                    console.print("[red]Mapping cancelled[/red]")
                    raise typer.Exit(1)

                save_mapping(mapping, settings.mappings_file)
            else:
                console.print(f"[green]✓[/green] Using saved mapping for {mapping.bank_name}")

            # Parse and extract all fields with mapping
            parsed_transactions = parser.load_with_mapping(file, mapping)
            console.print(f"[green]✓[/green] Loaded {len(parsed_transactions)} transactions")
            all_parsed_transactions.extend(parsed_transactions)

        # Step 2: Categorize with LLM and create StandardTransactions
        console.print("\n[cyan]Categorizing transactions with local LLM...[/cyan]")
        categorizer = LLMCategorizer()
        currency_converter = CurrencyConverter()

        standardized: list[StandardTransaction] = []
        for parsed in all_parsed_transactions:
            # Categorize using description
            categorized = categorizer.categorize(parsed.description)

            # Convert currency to DKK
            amount_dkk = currency_converter.convert(
                amount=parsed.amount,
                from_currency=parsed.currency,
                to_currency="DKK",
                transaction_date=parsed.date,
            )

            # Create standardized transaction
            standardized.append(
                StandardTransaction(
                    date=parsed.date,
                    category=categorized.category,
                    subcategory=categorized.subcategory,
                    amount=amount_dkk,
                    source=parsed.source,
                    description=parsed.description,
                    confidence=categorized.confidence,
                )
            )

        console.print(f"[green]✓[/green] Categorized and normalized {len(standardized)} transactions")

        # Step 4: Confirm uncertain categories
        standardized = confirm_uncertain_categories(standardized)
        if not standardized:
            console.print("[red]No transactions to export, exiting...[/red]")
            raise typer.Exit(1)

        # Step 5: Export
        output_file = output or (settings.output_dir / settings.default_output_filename)
        exporter = CSVExporter()
        result_file = exporter.export(standardized, output_file)

        console.print("\n[bold green]✓ Success![/bold green]")
        console.print(f"Output written to: {result_file}")

        # Print summary
        print_summary(standardized)

    @app.command()
    def list_mappings(ctx: typer.Context) -> None:
        """List all saved bank mappings"""
        settings: Settings = ctx.obj["settings"]

        if not settings.mappings_file.exists():
            console.print("No saved mappings found.")
            return

        with settings.mappings_file.open() as f:
            mappings = json.load(f)

        console.print("\n[bold]Saved Bank Mappings:[/bold]")
        for bank_name in mappings:
            console.print(f"  • {bank_name}")

    return app


# Create default app instance for CLI entry point
app = create_app()


if __name__ == "__main__":
    app()
