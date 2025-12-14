#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.0",
#     "rich>=13.0.0",
#     "pyyaml>=6.0",
#     "beautifulsoup4>=4.12.0",
#     "lxml>=5.0.0",
#     "playwright>=1.40.0",
#     "claude-agent-sdk>=0.1.0",
# ]
# ///

"""
ExtractorPatternAgent CLI

Command-line interface for generating and managing web scraping extraction patterns
using Claude AI agent.
"""

import click
import asyncio
import json
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent import ExtractorPatternAgent

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    ExtractorPatternAgent CLI - AI-powered web scraping pattern generator.

    Generate reliable extraction patterns for e-commerce product pages using
    Claude AI agent with specialized web scraping tools.
    """
    pass


@cli.command()
@click.argument('url')
@click.option('--save/--no-save', default=True, help='Save patterns to database')
@click.option('--output', '-o', type=click.Path(), help='Save patterns to JSON file')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def generate(url, save, output, config, verbose):
    """
    Generate extraction patterns for a product URL.

    Example:
        extractor-cli.py generate https://www.example.com/product/123
    """
    console.print(Panel.fit(
        f"[bold cyan]Generating Extraction Patterns[/bold cyan]\n\n"
        f"URL: {url}",
        border_style="cyan"
    ))

    async def run():
        try:
            # Initialize agent
            with console.status("[bold green]Initializing agent...", spinner="dots"):
                agent_config = None
                if config:
                    import yaml
                    with open(config, 'r') as f:
                        agent_config = yaml.safe_load(f)

                async with ExtractorPatternAgent(config=agent_config) as agent:
                    console.print("✓ Agent initialized\n")

                    # Generate patterns
                    console.print("[bold]Generating patterns...[/bold]")
                    patterns = await agent.generate_patterns(url, save_to_db=save)

                    # Display results
                    if "patterns" in patterns:
                        console.print("\n[bold green]✓ Patterns Generated Successfully[/bold green]\n")

                        # Create table
                        table = Table(title="Extraction Patterns", show_header=True)
                        table.add_column("Field", style="cyan")
                        table.add_column("Type", style="magenta")
                        table.add_column("Selector", style="yellow")
                        table.add_column("Confidence", style="green")

                        for field_name, field_pattern in patterns["patterns"].items():
                            primary = field_pattern.get("primary", {})
                            table.add_row(
                                field_name,
                                primary.get("type", "N/A"),
                                primary.get("selector", "N/A")[:50],
                                f"{primary.get('confidence', 0.0):.2f}"
                            )

                        console.print(table)

                        # Show metadata
                        if "metadata" in patterns:
                            meta = patterns["metadata"]
                            console.print(f"\n[bold]Metadata:[/bold]")
                            console.print(f"  Validated: {meta.get('validated_count', 0)}")
                            console.print(f"  Confidence: {meta.get('confidence_score', 0.0):.2f}")

                        # Save to file if requested
                        if output:
                            output_path = Path(output)
                            with open(output_path, 'w') as f:
                                json.dump(patterns, f, indent=2)
                            console.print(f"\n✓ Patterns saved to: {output_path}")

                        if save:
                            console.print("\n✓ Patterns saved to database")

                    else:
                        console.print("[bold red]✗ Pattern generation failed[/bold red]")
                        if verbose:
                            console.print(f"\nResponse: {json.dumps(patterns, indent=2)}")

                        sys.exit(1)

        except Exception as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            if verbose:
                import traceback
                console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(run())


@cli.command()
@click.argument('url')
@click.option('--patterns', '-p', type=click.Path(exists=True), help='Patterns JSON file')
@click.option('--domain', '-d', help='Load patterns from database by domain')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def validate(url, patterns, domain, config, verbose):
    """
    Validate extraction patterns against a URL.

    Example:
        extractor-cli.py validate https://www.example.com/product/456 -d example.com
    """
    console.print(Panel.fit(
        f"[bold cyan]Validating Extraction Patterns[/bold cyan]\n\n"
        f"URL: {url}",
        border_style="cyan"
    ))

    async def run():
        try:
            agent_config = None
            if config:
                import yaml
                with open(config, 'r') as f:
                    agent_config = yaml.safe_load(f)

            async with ExtractorPatternAgent(config=agent_config) as agent:
                console.print("✓ Agent initialized\n")

                # Load patterns if file provided
                pattern_data = None
                if patterns:
                    with open(patterns, 'r') as f:
                        pattern_data = json.load(f)
                    console.print(f"✓ Loaded patterns from: {patterns}\n")

                # Validate
                console.print("[bold]Validating patterns...[/bold]")
                validation = await agent.validate_patterns(url, pattern_data)

                # Display results
                if isinstance(validation, dict) and "success" in validation:
                    success = validation.get("success", False)
                    confidence = validation.get("overall_confidence", 0.0)

                    status = "[bold green]✓ PASSED[/bold green]" if success else "[bold red]✗ FAILED[/bold red]"
                    console.print(f"\n{status}")
                    console.print(f"Overall Confidence: {confidence:.2f}\n")

                    # Field results
                    field_validations = validation.get("field_validations", {})
                    if field_validations:
                        table = Table(title="Field Validation Results")
                        table.add_column("Field", style="cyan")
                        table.add_column("Status", style="bold")
                        table.add_column("Confidence", style="yellow")
                        table.add_column("Value", style="dim")

                        for field_name, field_result in field_validations.items():
                            field_success = field_result.get("valid", False)
                            field_conf = field_result.get("confidence", 0.0)
                            field_value = str(field_result.get("value", ""))[:50]

                            status_icon = "✓" if field_success else "✗"
                            status_color = "green" if field_success else "red"

                            table.add_row(
                                field_name,
                                f"[{status_color}]{status_icon}[/{status_color}]",
                                f"{field_conf:.2f}",
                                field_value
                            )

                        console.print(table)

                    sys.exit(0 if success else 1)

                else:
                    console.print("[bold red]✗ Validation failed[/bold red]")
                    if verbose:
                        console.print(f"\nResponse: {json.dumps(validation, indent=2)}")
                    sys.exit(1)

        except Exception as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            if verbose:
                import traceback
                console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(run())


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
def list_patterns(config):
    """
    List all stored extraction patterns.

    Example:
        extractor-cli.py list
    """
    console.print(Panel.fit(
        "[bold cyan]Stored Extraction Patterns[/bold cyan]",
        border_style="cyan"
    ))

    async def run():
        try:
            agent_config = None
            if config:
                import yaml
                with open(config, 'r') as f:
                    agent_config = yaml.safe_load(f)

            async with ExtractorPatternAgent(config=agent_config) as agent:
                result = await agent.list_stored_patterns()

                if isinstance(result, dict) and "patterns" in result:
                    patterns = result["patterns"]

                    if patterns:
                        table = Table(show_header=True)
                        table.add_column("Domain", style="cyan")
                        table.add_column("Confidence", style="green")
                        table.add_column("Created", style="yellow")
                        table.add_column("Validations", style="magenta")

                        for pattern in patterns:
                            table.add_row(
                                pattern.get("domain", "N/A"),
                                f"{pattern.get('confidence', 0.0):.2f}",
                                pattern.get("created_at", "N/A")[:19],
                                str(pattern.get("validation_count", 0))
                            )

                        console.print(table)
                        console.print(f"\n[bold]Total:[/bold] {len(patterns)} patterns")
                    else:
                        console.print("\n[dim]No patterns stored yet[/dim]")

        except Exception as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(run())


@cli.command()
@click.argument('domain')
@click.option('--output', '-o', type=click.Path(), help='Save to JSON file')
def export(domain, output):
    """
    Export patterns for a domain to JSON file.

    Example:
        extractor-cli.py export example.com -o patterns.json
    """
    async def run():
        try:
            async with ExtractorPatternAgent() as agent:
                result = await agent.query(f"Load patterns for domain '{domain}'")

                if output:
                    with open(output, 'w') as f:
                        json.dump(result, f, indent=2)
                    console.print(f"✓ Patterns exported to: {output}")
                else:
                    console.print(json.dumps(result, indent=2))

        except Exception as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(run())


@cli.command()
@click.argument('query')
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
def query(query, config):
    """
    Send a custom query to the agent.

    Example:
        extractor-cli.py query "What tools are available?"
    """
    async def run():
        try:
            agent_config = None
            if config:
                import yaml
                with open(config, 'r') as f:
                    agent_config = yaml.safe_load(f)

            async with ExtractorPatternAgent(config=agent_config) as agent:
                console.print(f"[bold]Query:[/bold] {query}\n")

                with console.status("[bold green]Processing...", spinner="dots"):
                    result = await agent.query(query)

                console.print("\n[bold]Response:[/bold]")
                if isinstance(result, dict):
                    console.print(json.dumps(result, indent=2))
                else:
                    console.print(str(result))

        except Exception as e:
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            sys.exit(1)

    asyncio.run(run())


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
