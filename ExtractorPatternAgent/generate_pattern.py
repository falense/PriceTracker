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
import re
import logging
import argparse
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from urllib.parse import urlparse
import structlog

# Add src to path for stealth utilities
sys.path.insert(0, str(Path(__file__).parent / "src"))
from utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options

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


async def fetch_page(url):
    """Fetch page with comprehensive stealth to avoid bot detection."""
    if logger:
        logger.info("fetch_page_started", url=url)
    else:
        console.print(f"[cyan]Fetching page:[/cyan] {url}")

    async with async_playwright() as p:
        # Launch with stealth arguments
        browser = await p.chromium.launch(
            headless=True,  # Required for Docker/server environments
            args=STEALTH_ARGS
        )

        # Create context with stealth options
        context_options = get_stealth_context_options()
        context = await browser.new_context(**context_options)

        page = await context.new_page()

        # Apply comprehensive stealth script
        await apply_stealth(page)

        try:
            # Navigate with realistic behavior
            await page.goto(url, wait_until='load', timeout=60000)

            # Wait for dynamic content (more realistic timing)
            await page.wait_for_timeout(2000)

            html = await page.content()
            if logger:
                logger.info("fetch_page_completed", url=url, html_length=len(html))
            else:
                console.print(f"[green]✓[/green] Page fetched ({len(html)} bytes)")
            return html
        finally:
            await browser.close()


def analyze_html(html, url):
    """Analyze HTML and generate extraction patterns."""
    if logger:
        logger.info("analyze_html_started", url=url)
    else:
        console.print("\n[cyan]Analyzing HTML structure...[/cyan]")

    soup = BeautifulSoup(html, 'html.parser')
    # Normalize domain by removing www prefix for consistency
    domain = urlparse(url).netloc.replace('www.', '').lower()
    patterns = {
        "store_domain": domain,
        "url": url,
        "patterns": {}
    }

    # Extract Price
    if logger:
        logger.info("extracting_field", field="price")
    else:
        console.print("  [yellow]→[/yellow] Finding price patterns...")
    price_pattern = None

    # Try data-price attribute
    price_elem = soup.select_one('[data-price]')
    if price_elem:
        price_value = price_elem.get('data-price')
        selector = f"#{price_elem.get('id')}" if price_elem.get('id') else f".{price_elem.get('class')[0]}"
        price_pattern = {
            "primary": {
                "type": "css",
                "selector": selector,
                "attribute": "data-price",
                "confidence": 0.95,
                "sample_value": price_value
            },
            "fallbacks": []
        }
        if logger:
            logger.info("pattern_found", field="price", selector=selector, sample_value=price_value)
        else:
            console.print(f"    [green]✓[/green] Found: {selector} → {price_value}")

    # Try price class names
    if not price_pattern:
        price_elems = soup.find_all(class_=lambda c: c and 'price' in str(c).lower())
        for elem in price_elems[:3]:
            text = elem.get_text(strip=True)
            if re.search(r'\d+[.,]?\d*', text):
                classes = elem.get('class', [])
                selector = f".{classes[0]}" if classes else elem.name
                price_pattern = {
                    "primary": {
                        "type": "css",
                        "selector": selector,
                        "confidence": 0.85,
                        "sample_value": text
                    },
                    "fallbacks": []
                }
                console.print(f"    [green]✓[/green] Found: {selector} → {text}")
                break

    if price_pattern:
        patterns["patterns"]["price"] = price_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="price")
        else:
            console.print("    [red]✗[/red] No price pattern found")

    # Extract Title
    if logger:
        logger.info("extracting_field", field="title")
    else:
        console.print("  [yellow]→[/yellow] Finding title patterns...")
    title_pattern = None

    # Try Open Graph
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get('content'):
        title_pattern = {
            "primary": {
                "type": "meta",
                "selector": 'meta[property="og:title"]',
                "attribute": "content",
                "confidence": 0.95,
                "sample_value": og_title.get('content')
            },
            "fallbacks": []
        }
        if logger:
            logger.info("pattern_found", field="title", selector='og:title', sample_value=og_title.get('content')[:50])
        else:
            console.print(f"    [green]✓[/green] Found: og:title → {og_title.get('content')[:50]}...")

    # Try h1 as fallback
    if not title_pattern:
        h1 = soup.find('h1')
        if h1:
            text = h1.get_text(strip=True)
            title_pattern = {
                "primary": {
                    "type": "css",
                    "selector": "h1",
                    "confidence": 0.85,
                    "sample_value": text
                },
                "fallbacks": []
            }
            if logger:
                logger.info("pattern_found", field="title", selector='h1', sample_value=text[:50])
            else:
                console.print(f"    [green]✓[/green] Found: h1 → {text[:50]}...")

    if title_pattern:
        # Add h1 as fallback if og:title was primary
        if title_pattern["primary"]["type"] == "meta":
            h1 = soup.find('h1')
            if h1:
                title_pattern["fallbacks"].append({
                    "type": "css",
                    "selector": "h1",
                    "confidence": 0.85
                })
        patterns["patterns"]["title"] = title_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="title")
        else:
            console.print("    [red]✗[/red] No title pattern found")

    # Extract Image
    if logger:
        logger.info("extracting_field", field="image")
    else:
        console.print("  [yellow]→[/yellow] Finding image patterns...")
    image_pattern = None

    # Try Open Graph
    og_image = soup.select_one('meta[property="og:image:secure_url"], meta[property="og:image"]')
    if og_image and og_image.get('content'):
        image_pattern = {
            "primary": {
                "type": "meta",
                "selector": 'meta[property="og:image:secure_url"]',
                "attribute": "content",
                "confidence": 0.95,
                "sample_value": og_image.get('content')
            },
            "fallbacks": [{
                "type": "meta",
                "selector": 'meta[property="og:image"]',
                "attribute": "content",
                "confidence": 0.95
            }]
        }
        if logger:
            logger.info("pattern_found", field="image", selector='og:image', sample_value=og_image.get('content')[:60])
        else:
            console.print(f"    [green]✓[/green] Found: og:image → {og_image.get('content')[:60]}...")

    if image_pattern:
        patterns["patterns"]["image"] = image_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="image")
        else:
            console.print("    [red]✗[/red] No image pattern found")

    # Extract Availability/Stock
    if logger:
        logger.info("extracting_field", field="availability")
    else:
        console.print("  [yellow]→[/yellow] Finding availability patterns...")
    avail_pattern = None

    # Look for stock-related elements
    stock_elems = soup.find_all(class_=lambda c: c and any(
        kw in str(c).lower() for kw in ['stock', 'availability', 'avail', 'lager']
    ))

    for elem in stock_elems[:3]:
        text = elem.get_text(strip=True)
        if text:
            classes = elem.get('class', [])
            selector = f".{classes[0]}" if classes else elem.name

            # Check if it has a title attribute (often more reliable)
            title = elem.get('title')
            if title:
                avail_pattern = {
                    "primary": {
                        "type": "css",
                        "selector": selector,
                        "attribute": "title",
                        "confidence": 0.90,
                        "sample_value": title
                    },
                    "fallbacks": [{
                        "type": "css",
                        "selector": selector,
                        "confidence": 0.85
                    }]
                }
                if logger:
                    logger.info("pattern_found", field="availability", selector=selector, sample_value=title)
                else:
                    console.print(f"    [green]✓[/green] Found: {selector} → {title}")
                break
            else:
                avail_pattern = {
                    "primary": {
                        "type": "css",
                        "selector": selector,
                        "confidence": 0.80,
                        "sample_value": text
                    },
                    "fallbacks": []
                }
                console.print(f"    [green]✓[/green] Found: {selector} → {text}")
                break

    if avail_pattern:
        patterns["patterns"]["availability"] = avail_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="availability")
        else:
            console.print("    [red]✗[/red] No availability pattern found")

    # Extract Article Number (Varenummer/SKU)
    if logger:
        logger.info("extracting_field", field="article_number")
    else:
        console.print("  [yellow]→[/yellow] Finding article number patterns...")
    article_pattern = None

    # Try itemprop="sku"
    sku_elem = soup.select_one('[itemprop="sku"]')
    if sku_elem:
        sku_value = sku_elem.get_text(strip=True)
        article_pattern = {
            "primary": {
                "type": "css",
                "selector": '[itemprop="sku"]',
                "confidence": 0.95,
                "sample_value": sku_value
            },
            "fallbacks": []
        }
        if logger:
            logger.info("pattern_found", field="article_number", selector='[itemprop="sku"]', sample_value=sku_value)
        else:
            console.print(f"    [green]✓[/green] Found: [itemprop='sku'] → {sku_value}")

    # Try searching for "Varenummer" or "Article" labels
    if not article_pattern:
        for label in soup.find_all(['span', 'div', 'dt']):
            label_text = label.get_text(strip=True).lower()
            if any(kw in label_text for kw in ['varenummer', 'artikkel', 'article', 'sku', 'item number']):
                # Look for value in next sibling or parent
                value_elem = label.find_next_sibling()
                if value_elem:
                    value = value_elem.get_text(strip=True)
                    if value and value.isdigit():
                        article_pattern = {
                            "primary": {
                                "type": "css",
                                "selector": f"{label.name} + {value_elem.name}",
                                "confidence": 0.85,
                                "sample_value": value
                            },
                            "fallbacks": []
                        }
                        console.print(f"    [green]✓[/green] Found: {label_text} → {value}")
                        break

    if article_pattern:
        patterns["patterns"]["article_number"] = article_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="article_number")
        else:
            console.print("    [red]✗[/red] No article number pattern found")

    # Extract Model Number (Manufacturer number)
    if logger:
        logger.info("extracting_field", field="model_number")
    else:
        console.print("  [yellow]→[/yellow] Finding model number patterns...")
    model_pattern = None

    # Try searching in JSON data attributes (common in e-commerce sites)
    json_elems = soup.find_all(attrs={"data-initobject": True})
    for elem in json_elems:
        try:
            import json as json_lib
            from html import unescape
            data_str = elem.get('data-initobject', '')
            # Unescape HTML entities (handles &quot; etc)
            data_str = unescape(data_str)
            data = json_lib.loads(data_str)

            # Look for manufacturer number in various fields
            model_num = None
            json_path = None

            # Check trackingData first (most common)
            if 'trackingData' in data:
                for key in ['item_manufacturer_number', 'manufacturerNumber', 'model_number', 'modelNumber', 'mpn']:
                    if key in data['trackingData']:
                        model_num = data['trackingData'][key]
                        json_path = f"trackingData.{key}"
                        break

            # Check root level
            if not model_num:
                for key in ['item_manufacturer_number', 'manufacturerNumber', 'model_number', 'modelNumber', 'mpn']:
                    if key in data:
                        model_num = data[key]
                        json_path = key
                        break

            if model_num:
                classes = elem.get('class', [])
                selector = f".{classes[0]}" if classes else f"{elem.name}"
                model_pattern = {
                    "primary": {
                        "type": "json",
                        "selector": selector,
                        "attribute": "data-initobject",
                        "json_path": json_path,
                        "confidence": 0.90,
                        "sample_value": model_num
                    },
                    "fallbacks": []
                }
                if logger:
                    logger.info("pattern_found", field="model_number", selector=selector, sample_value=model_num)
                else:
                    console.print(f"    [green]✓[/green] Found: JSON data → {model_num}")
                break
        except Exception as e:
            # Silently continue to next element
            continue

    # Try searching for "Model" or "Produsent" labels
    if not model_pattern:
        for label in soup.find_all(['span', 'div', 'dt', 'th']):
            label_text = label.get_text(strip=True).lower()
            if any(kw in label_text for kw in ['modell', 'model', 'produsent', 'manufacturer', 'mpn', 'part number']):
                # Look for value in next sibling or parent
                value_elem = label.find_next_sibling() or label.find_next(['td', 'dd', 'span'])
                if value_elem:
                    value = value_elem.get_text(strip=True)
                    if value and len(value) > 3:
                        model_pattern = {
                            "primary": {
                                "type": "css",
                                "selector": f"{label.name}:contains('{label_text[:10]}') + {value_elem.name}",
                                "confidence": 0.75,
                                "sample_value": value
                            },
                            "fallbacks": []
                        }
                        if logger:
                            logger.info("pattern_found", field="model_number", selector=f"{label.name}:contains('{label_text[:10]}') + {value_elem.name}", sample_value=value)
                        else:
                            console.print(f"    [green]✓[/green] Found: {label_text} → {value}")
                        break

    if model_pattern:
        patterns["patterns"]["model_number"] = model_pattern
    else:
        if logger:
            logger.warning("pattern_not_found", field="model_number")
        else:
            console.print("    [red]✗[/red] No model number pattern found")

    # Calculate overall confidence
    confidences = []
    for field_pattern in patterns["patterns"].values():
        confidences.append(field_pattern["primary"]["confidence"])

    patterns["metadata"] = {
        "fields_found": len(patterns["patterns"]),
        "total_fields": 6,
        "overall_confidence": sum(confidences) / len(confidences) if confidences else 0.0
    }

    if logger:
        logger.info("analyze_html_completed",
                   fields_found=patterns["metadata"]["fields_found"],
                   overall_confidence=patterns["metadata"]["overall_confidence"])

    return patterns


async def generate_patterns(url, log_format='console'):
    """Main function to generate patterns from URL."""

    if log_format == 'console':
        console.print(Panel.fit(
            f"[bold cyan]Pattern Generator[/bold cyan]\n\nURL: {url}",
            border_style="cyan"
        ))
    elif logger:
        logger.info("pattern_generation_started", url=url)

    # Fetch page
    html = await fetch_page(url)

    # Analyze and generate patterns
    patterns = analyze_html(html, url)

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
    elif logger:
        logger.info("pattern_generation_completed",
                   output_file=output_file,
                   store_domain=patterns['store_domain'],
                   fields_found=patterns['metadata']['fields_found'],
                   confidence=patterns['metadata']['overall_confidence'])

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
        patterns = asyncio.run(generate_patterns(url, log_format))
        if log_format == 'console':
            console.print("\n[bold green]✓ SUCCESS[/bold green]")
        else:
            logger.info("pattern_generation_success")
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
