from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

from budget_tracker.analytics.engine import AnalyticsEngine
from budget_tracker.cli.blacklist import interactive_blacklist_management
from budget_tracker.cli.confirmation import categorize_transactions
from budget_tracker.cli.mapping import interactive_column_mapping, load_mapping, save_mapping
from budget_tracker.cli.period_selection import parse_period_flags, resolve_period
from budget_tracker.cli.transfer_confirmation import confirm_transfers
from budget_tracker.config.settings import Settings, get_settings
from budget_tracker.currency.converter import CurrencyConverter
from budget_tracker.exporters import CSVExporter, ExcelExporter, GoogleSheetsExporter
from budget_tracker.exporters.terminal_renderer import TerminalRenderer
from budget_tracker.filters import TransferDetector
from budget_tracker.models.transaction import StandardTransaction
from budget_tracker.parsers.csv_parser import CSVParser, ParsedTransaction

console = Console()


def create_app(settings: Settings | None = None) -> typer.Typer:  # noqa: PLR0915
    """Create the Typer app with injected settings.

    Args:
        settings: Settings instance to use. If None, uses get_settings().

    Returns:
        Configured Typer app.
    """
    app = typer.Typer(
        help="Bank Statement Normalizer - Standardize and categorize your transactions"
    )
    _settings = settings or get_settings()

    @app.callback()
    def main_callback(ctx: typer.Context) -> None:
        """Initialize the app with settings."""
        ctx.ensure_object(dict)
        ctx.obj["settings"] = _settings

    @app.command()
    def process(  # noqa: PLR0915, PLR0912, PLR0913
        ctx: typer.Context,
        files: Annotated[list[Path], typer.Argument(help="CSV files to process")],
        banks: Annotated[
            list[str],
            typer.Option(
                "--banks", "-b", help="Bank name(s) for mapping lookup. Must match number of files."
            ),
        ],
        output: Annotated[
            Path | None, typer.Option("--output", "-o", help="Output file path")
        ] = None,
        csv: Annotated[bool, typer.Option("--csv", help="Export as CSV instead of Excel.")] = False,
        sheets: Annotated[bool, typer.Option("--sheets", help="Export to Google Sheets.")] = False,
        from_date: Annotated[
            str | None,
            typer.Option("--from-date", help="Start date for analytics period (YYYY-MM-DD)"),
        ] = None,
        to_date: Annotated[
            str | None,
            typer.Option("--to-date", help="End date for analytics period (YYYY-MM-DD)"),
        ] = None,
    ) -> None:
        """
        Process bank statement CSV files and generate standardized output.

        Examples:
            budget-tracker process bank1.csv
            budget-tracker process bank1.csv -b danske_bank --sheets
            budget-tracker process bank1.csv bank2.csv --output results.csv
        """
        settings: Settings = ctx.obj["settings"]

        console.print("[bold]Budget Tracker - Bank Statement Normalizer[/bold]\n")

        # Ensure directories exist
        settings.ensure_directories()

        if len(files) != len(banks):
            console.print(
                f"[red]✗[/red] Number of banks ({len(banks)}) "
                f"must match number of files ({len(files)})."
            )
            console.print("Usage: budget-tracker process file1.csv file2.csv --banks bank1 bank2")
            console.print("Run 'budget-tracker list-mappings' to see available bank names.")
            raise typer.Exit(1)

        # Validate date flags early (before any interactive work)
        if from_date is not None or to_date is not None:
            parse_period_flags(from_date, to_date)

        # Setup
        parser = CSVParser()
        all_parsed_transactions: list[ParsedTransaction] = []

        # Validate input files
        for i, file in enumerate(files):
            console.print(f"\n[cyan]Processing:[/cyan] {file.name}")

            mapping = load_mapping(banks[i], settings.banks_dir)

            if not mapping:
                # Interactive column mapping
                _, columns = parser.parse_file(file)
                console.print(f"Detected {len(columns)} columns: {', '.join(columns)}")
                console.print(
                    f"[yellow]No mapping found for '{banks[i]}'. Creating new mapping...[/yellow]"
                )

                mapping = interactive_column_mapping(columns, bank_name=banks[i])
                if not mapping:
                    console.print("[red]Mapping cancelled[/red]")
                    raise typer.Exit(1)

                save_mapping(mapping, settings.banks_dir)
            else:
                console.print(f"[green]✓[/green] Using saved mapping for {mapping.bank_name}")

            # Parse and extract all fields with mapping
            parsed_transactions = parser.load_with_mapping(file, mapping)
            console.print(f"[green]✓[/green] Loaded {len(parsed_transactions)} transactions")
            all_parsed_transactions.extend(parsed_transactions)

        # Step 1.5: Detect internal transfers
        console.print("\n[cyan]Detecting internal transfers...[/cyan]")
        detector = TransferDetector()
        transfer_pairs, non_transfer_transactions = detector.detect(all_parsed_transactions)

        # Confirm transfers with user
        confirmed_transfers, rejected_transfers = confirm_transfers(transfer_pairs)

        if confirmed_transfers:
            console.print(
                f"[green]✓[/green] {len(confirmed_transfers)} transfer(s) "
                "will be marked as Internal Transfer"
            )

        # Rebuild transaction list: rejected transfers go back to normal processing
        transactions_to_categorize = non_transfer_transactions.copy()
        for pair in rejected_transfers:
            transactions_to_categorize.append(pair.outgoing)
            transactions_to_categorize.append(pair.incoming)

        # Step 2: Categorize transactions with user selection
        console.print("\n[cyan]Categorizing transactions...[/cyan]")
        currency_converter = CurrencyConverter()

        standardized: list[StandardTransaction] = []

        # First, add confirmed transfers
        for pair in confirmed_transfers:
            for parsed in [pair.outgoing, pair.incoming]:
                amount_dkk = currency_converter.convert(
                    amount=parsed.amount,
                    from_currency=parsed.currency,
                    to_currency="DKK",
                    transaction_date=parsed.date,
                )
                standardized.append(
                    StandardTransaction(
                        date=parsed.date,
                        category="Internal Transfer",
                        subcategory="Transfer",
                        amount=amount_dkk,
                        source=parsed.source,
                        description=parsed.description,
                    )
                )

        # Categorize remaining transactions via user selection
        if transactions_to_categorize:
            user_categorized = categorize_transactions(
                _settings, transactions_to_categorize, currency_converter
            )
            standardized.extend(user_categorized)

        console.print(
            f"[green]✓[/green] Categorized and normalized {len(standardized)} transactions"
        )

        if not standardized:
            console.print("[red]No transactions to export, exiting...[/red]")
            raise typer.Exit(1)

        # Compute analytics (used by Excel exporter and terminal renderer)
        period = resolve_period(from_date, to_date, standardized, settings.no_interactive)
        analytics = AnalyticsEngine().compute(standardized, period)

        # Filter transactions to the selected period for export
        filtered = [
            t for t in standardized
            if (period.from_date is None or t.date >= period.from_date)
            and (period.to_date is None or t.date <= period.to_date)
        ]

        if not filtered:
            console.print("[red]No transactions in selected period, exiting...[/red]")
            raise typer.Exit(1)

        # Step 5: Export
        output_file = output or (settings.output_dir / settings.default_output_filename)

        if csv:
            if output_file.suffix == ".xlsx":
                output_file = output_file.with_suffix(".csv")
            file_exporter: CSVExporter | ExcelExporter = CSVExporter(
                _settings, output_file=output_file
            )
        else:
            file_exporter = ExcelExporter(
                _settings, analytics_result=analytics, output_file=output_file
            )

        result_path = file_exporter.export(filtered)
        console.print("\n[bold green]✓ Success![/bold green]")
        console.print(f"Output written to: {result_path}")

        # Optionally export to Google Sheets
        if sheets:
            console.print("\n[cyan]Exporting to Google Sheets...[/cyan]")
            try:
                sheets_exporter = GoogleSheetsExporter(_settings)
                sheets_result = sheets_exporter.export(filtered)
                console.print(f"[green]✓[/green] {sheets_result}")
            except Exception as e:
                console.print(f"[red]✗[/red] Google Sheets export failed: {e}")
                console.print("[yellow]File export completed successfully.[/yellow]")

        # Display terminal analytics
        TerminalRenderer(console).render(analytics)

    @app.command()
    def list_mappings(ctx: typer.Context) -> None:
        """List all saved bank mappings"""
        settings: Settings = ctx.obj["settings"]

        if not settings.banks_dir.exists():
            console.print("No saved mappings found.")
            return

        yaml_files = list(settings.banks_dir.glob("*.yaml"))

        if not yaml_files:
            console.print("No saved mappings found.")
            return

        console.print("[bold]Saved Bank Mappings:[/bold]\n")
        for yaml_file in sorted(yaml_files):
            bank_name = yaml_file.stem
            console.print(f"  • {bank_name}")

    @app.command()
    def blacklist(ctx: typer.Context) -> None:
        """Interactively manage blacklist keywords for bank configurations"""
        settings: Settings = ctx.obj["settings"]
        interactive_blacklist_management(settings.banks_dir)

    @app.command()
    def clear_categories(ctx: typer.Context) -> None:
        """Clear all saved category mappings, so transactions are re-prompted on next run."""
        settings: Settings = ctx.obj["settings"]
        mappings_file = settings.category_mappings_file

        if not mappings_file.exists():
            console.print("No saved category mappings found.")
            return

        count = 0
        raw = yaml.safe_load(mappings_file.read_text())
        if isinstance(raw, dict):
            count = len(raw)

        confirm = typer.confirm(f"Delete {count} saved category mapping(s)?")
        if not confirm:
            console.print("Cancelled.")
            return

        mappings_file.unlink()
        console.print("[green]✓[/green] Category mappings cleared.")

    return app


# Create default app instance for CLI entry point
app = create_app()


if __name__ == "__main__":
    app()
