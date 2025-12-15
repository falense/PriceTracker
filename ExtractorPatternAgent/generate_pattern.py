#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.40.0",
#     "beautifulsoup4>=4.12.0",
#     "lxml>=5.0.0",
#     "rich>=13.0.0",
# ]
# ///

"""
Simple pattern generator - input URL, get extraction patterns

Usage:
    python generate_pattern.py <url>
    python generate_pattern.py https://www.komplett.no/product/1310167/...
"""

import asyncio
import json
import sys
import logging
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
import structlog

from ExtractorPatternAgent import PatternGenerator

console = Console()
logger = None  # Will be initialized based on log format


def setup_logging(log_format='console'):
    """Configure structured logging based on format."""
    global logger

    if log_format == 'json':
        # JSON output for parsing
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.CallsiteParameterAdder(
                    [structlog.processors.CallsiteParameter.FILENAME]
                ),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )
    else:
        # Console output for human readability
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

    logger = structlog.get_logger()
    return logger




async def generate_patterns(url, domain=None, log_format='console'):
    """Main function to generate patterns from URL."""

    if log_format == 'console':
        console.print(Panel.fit(
            f"[bold cyan]Pattern Generator[/bold cyan]\n\nURL: {url}",
            border_style="cyan"
        ))

    # Create generator with appropriate logger
    generator = PatternGenerator(logger=logger)

    # Generate patterns
    patterns = await generator.generate(url, domain=domain)

    # Display summary
    if log_format == 'console':
        console.print(f"\n[bold green]✓ Pattern Generation Complete[/bold green]\n")
        console.print(f"Store Domain: {patterns['store_domain']}")
        console.print(f"Fields Found: {patterns['metadata']['fields_found']}/6")
        console.print(f"Confidence: {patterns['metadata']['overall_confidence']:.2%}\n")

    # Save to file
    output_file = f"{patterns['store_domain'].replace('.', '_')}_patterns.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(patterns, f, indent=2, ensure_ascii=False)

    if log_format == 'console':
        console.print(f"[green]✓[/green] Patterns saved to: [cyan]{output_file}[/cyan]\n")
        # Pretty print patterns
        console.print("[bold]Generated Patterns:[/bold]")
        console.print(json.dumps(patterns, indent=2, ensure_ascii=False))

    return patterns


def main():
    parser = argparse.ArgumentParser(description="Generate extraction patterns for a product URL")
    parser.add_argument('url', help='Product URL to analyze')
    parser.add_argument('--domain', help='Domain name override (optional)')
    parser.add_argument('--log-format', choices=['console', 'json'], default='console',
                       help='Log output format (default: console)')

    args = parser.parse_args()

    url = args.url
    log_format = args.log_format

    if not url.startswith('http'):
        console.print("[red]Error:[/red] URL must start with http:// or https://")
        sys.exit(1)

    # Setup logging based on format
    global logger
    logger = setup_logging(log_format)

    try:
        patterns = asyncio.run(generate_patterns(url, args.domain, log_format))
        if log_format == 'console':
            console.print("\n[bold green]✓ SUCCESS[/bold green]")
    except KeyboardInterrupt:
        if log_format == 'console':
            console.print("\n\n[yellow]Interrupted by user[/yellow]")
        else:
            logger.warning("pattern_generation_interrupted")
        sys.exit(130)
    except Exception as e:
        if log_format == 'console':
            console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
            import traceback
            traceback.print_exc()
        else:
            logger.error("pattern_generation_failed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
