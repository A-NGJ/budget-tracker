import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from budget_tracker.categorizer.llm_categorizer import CategoryResult, LLMCategorizer
from budget_tracker.cli.confirmation import confirm_uncertain_categories
from budget_tracker.cli.mapping import interactive_column_mapping, load_mapping, save_mapping
from budget_tracker.config.settings import settings
from budget_tracker.exporters.csv_exporter import CSVExporter
from budget_tracker.exporters.summary import print_summary
from budget_tracker.models.transaction import RawTransaction  # noqa: TC001
from budget_tracker.normalizer.batch_processor import BatchNormalizer
from budget_tracker.parsers.csv_parser import CSVParser

app = typer.Typer(help="Bank Statement Normalizer - Standardize and categorize your transactions")
console = Console()


@app.command()
def process(
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
    console.print("[bold]Budget Tracker - Bank Statement Normalizer[/bold]\n")

    # Ensure directories exist
    settings.ensure_directories()

    # Validate input files
    for file in files:
        if not file.exists():
            console.print(f"[red]✗[/red] File not found: {file}")
            raise typer.Exit(1)

    console.print(f"Processing {len(files)} file(s)...")

    # Step 1: Parse and map columns
    parser = CSVParser()
    all_raw_transactions: list[RawTransaction] = []

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

        # Parse with mapping
        raw_transactions = parser.load_with_mapping(file, mapping)
        console.print(f"[green]✓[/green] Loaded {len(raw_transactions)} transactions")
        all_raw_transactions.extend(raw_transactions)

    # Step 2: Categorize with LLM
    console.print("\n[cyan]Categorizing transactions with local LLM...[/cyan]")
    categorizer = LLMCategorizer()

    categorized_transactions: list[CategoryResult] = []
    for raw in all_raw_transactions:
        # Get description for categorization
        desc = raw.data.get("description", "")
        result = categorizer.categorize(desc)

        # Create standardized transaction (will be normalized in next step)
        # For now, store category info
        categorized_transactions.append(result)

    console.print(f"[green]✓[/green] Categorized {len(all_raw_transactions)} transactions")

    # Step 3: Normalize
    console.print("\n[cyan]Normalizing data...[/cyan]")
    normalizer = BatchNormalizer()

    standardized = []
    for raw, categorized in zip(all_raw_transactions, categorized_transactions, strict=True):
        # Find the mapping used for this transaction
        mapping = load_mapping(Path(raw.source_file).stem, settings.mappings_file)
        if mapping:
            std = normalizer.normalizer.normalize(
                raw,
                mapping,
                category=categorized.category,
                subcategory=categorized.subcategory,
                confidence=categorized.confidence,
            )
            if std:
                standardized.append(std)

    console.print(f"[green]✓[/green] Normalized {len(standardized)} transactions")

    # Step 4: Confirm uncertain categories
    standardized = confirm_uncertain_categories(standardized)

    # Step 5: Export
    output_file = output or (settings.output_dir / settings.default_output_filename)
    exporter = CSVExporter()
    result_file = exporter.export(standardized, output_file)

    console.print("\n[bold green]✓ Success![/bold green]")
    console.print(f"Output written to: {result_file}")

    # Print summary
    print_summary(standardized)


@app.command()
def list_mappings() -> None:
    """List all saved bank mappings"""
    if not settings.mappings_file.exists():
        console.print("No saved mappings found.")
        return

    with settings.mappings_file.open() as f:
        mappings = json.load(f)

    console.print("\n[bold]Saved Bank Mappings:[/bold]")
    for bank_name in mappings:
        console.print(f"  • {bank_name}")


if __name__ == "__main__":
    app()
