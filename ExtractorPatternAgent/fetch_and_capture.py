#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.40.0",
# ]
# ///

"""
Fetch and capture web page artifacts for agent analysis.

This script fetches a web page using Playwright with comprehensive stealth
measures and saves two artifacts:
1. Complete rendered HTML
2. Full-page screenshot

Usage:
    python fetch_and_capture.py <url>
    python fetch_and_capture.py <url> -o /output/dir
    python fetch_and_capture.py <url> --quiet

Examples:
    python fetch_and_capture.py https://www.komplett.no/product/1310167
    uv run fetch_and_capture.py https://www.komplett.no/product/1310167
    python fetch_and_capture.py https://example.com -o /tmp/captures
"""

import asyncio
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Import stealth utilities
sys.path.insert(0, str(Path(__file__).parent / "src"))
from utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options


async def handle_cookie_dialog(page, quiet: bool = False):
    """
    Attempt to detect and accept cookie consent dialogs.

    Tries multiple common selectors used by cookie consent dialogs.
    Silently fails if no dialog is found.
    """
    # Common cookie dialog accept button selectors
    cookie_selectors = [
        # Generic
        'button:has-text("Accept")',
        'button:has-text("Agree")',
        'button:has-text("OK")',
        'button:has-text("Godta")',  # Norwegian: Accept
        'button:has-text("Godkjenn")',  # Norwegian: Approve
        'button:has-text("Aksepter")',  # Norwegian: Accept
        '[id*="accept"][id*="cookie"]',
        '[id*="consent"][id*="accept"]',
        '[class*="accept"][class*="cookie"]',
        '[class*="consent"][class*="accept"]',
        # CookieInformation (used by many Norwegian sites)
        '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
        '#CybotCookiebotDialogBodyButtonAccept',
        'a[id*="CybotCookiebotDialogBodyLevelButtonAccept"]',
        '.CookieInformation button[data-action="accept"]',
        # OneTrust
        '#onetrust-accept-btn-handler',
        'button[id*="onetrust-accept"]',
    ]

    for selector in cookie_selectors:
        try:
            # Wait for the button (short timeout)
            button = await page.wait_for_selector(selector, timeout=1000)
            if button:
                # Check if button is visible
                is_visible = await button.is_visible()
                if is_visible:
                    await button.click()
                    if not quiet:
                        print("✓ Cookie dialog accepted")
                    # Wait for dialog to disappear
                    await page.wait_for_timeout(1000)
                    return
        except:
            # Selector not found or timeout, try next one
            continue


async def fetch_and_capture(url: str, output_dir: str = ".", quiet: bool = False) -> tuple[str, str]:
    """
    Fetch a web page and capture both HTML and screenshot.

    Args:
        url: The URL to fetch
        output_dir: Directory to save output files (default: current directory)
        quiet: Suppress verbose output (default: False)

    Returns:
        Tuple of (html_file_path, screenshot_file_path)

    Raises:
        PlaywrightTimeoutError: If page load times out
        Exception: For other errors during fetch/capture
    """
    if not quiet:
        print(f"Fetching: {url}")

    async with async_playwright() as p:
        # Launch browser with stealth arguments
        browser = await p.chromium.launch(
            headless=True,
            args=STEALTH_ARGS
        )

        if not quiet:
            print("✓ Browser launched")

        try:
            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            # Create page and apply stealth
            page = await context.new_page()
            await apply_stealth(page)

            # Navigate to page
            start_time = datetime.now()
            await page.goto(url, wait_until='load', timeout=60000)

            # Wait for dynamic content to load
            await page.wait_for_timeout(2000)

            # Try to handle cookie consent dialogs
            await handle_cookie_dialog(page, quiet)

            elapsed = (datetime.now() - start_time).total_seconds()

            if not quiet:
                print(f"✓ Page loaded ({elapsed:.1f}s)")

            # Extract HTML
            html = await page.content()

            if not quiet:
                print(f"✓ HTML captured ({len(html):,} bytes)")

            # Capture screenshot (full page)
            screenshot_bytes = await page.screenshot(full_page=True, type='png')

            if not quiet:
                print(f"✓ Screenshot captured ({len(screenshot_bytes):,} bytes)")

            # Generate output filenames
            domain = urlparse(url).netloc.replace('www.', '')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            html_filename = f"{domain}_{timestamp}.html"
            screenshot_filename = f"{domain}_{timestamp}.png"

            # Create output directory if it doesn't exist
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            html_path = output_path / html_filename
            screenshot_path = output_path / screenshot_filename

            # Save artifacts
            html_path.write_text(html, encoding='utf-8')
            screenshot_path.write_bytes(screenshot_bytes)

            if not quiet:
                print(f"\nArtifacts saved:")
                print(f"  HTML:       {html_filename}")
                print(f"  Screenshot: {screenshot_filename}")

            return (str(html_path), str(screenshot_path))

        finally:
            await browser.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch web page and capture HTML + screenshot artifacts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s https://www.komplett.no/product/1310167
  %(prog)s https://example.com -o /tmp/captures
  %(prog)s https://example.com --quiet
        '''
    )

    parser.add_argument(
        'url',
        help='URL to fetch and capture'
    )

    parser.add_argument(
        '-o', '--output-dir',
        default='.',
        help='Output directory for artifacts (default: current directory)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )

    args = parser.parse_args()

    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://", file=sys.stderr)
        sys.exit(1)

    try:
        html_path, screenshot_path = asyncio.run(
            fetch_and_capture(args.url, args.output_dir, args.quiet)
        )

        # Output file paths for easy parsing by subprocess callers
        if args.quiet:
            print(f"HTML:{html_path}")
            print(f"Screenshot:{screenshot_path}")

        sys.exit(0)

    except PlaywrightTimeoutError:
        print("Error: Page load timeout (60s)", file=sys.stderr)
        sys.exit(2)

    except PermissionError as e:
        print(f"Error: Cannot write to output directory: {e}", file=sys.stderr)
        sys.exit(4)

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
