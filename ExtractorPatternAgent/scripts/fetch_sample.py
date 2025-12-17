#!/usr/bin/env python3
"""
Fetch web page sample (HTML + screenshot) for extractor development.

Usage:
    python scripts/fetch_sample.py https://www.komplett.no/product/1310167
    python scripts/fetch_sample.py <url> --domain komplett.no
    python scripts/fetch_sample.py <url> --quiet
"""

import asyncio
import sys
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options


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


class SampleFetcher:
    """Fetches and stores web page samples for extractor development."""

    def __init__(self, base_dir: Path = None):
        """
        Initialize SampleFetcher.

        Args:
            base_dir: Base directory for test_data (default: ../test_data)
        """
        if base_dir is None:
            # Default to test_data/ in ExtractorPatternAgent directory
            self.base_dir = Path(__file__).parent.parent / "test_data"
        else:
            self.base_dir = Path(base_dir)

    async def fetch_sample(
        self,
        url: str,
        domain: str = None,
        quiet: bool = False
    ) -> Path:
        """
        Fetch HTML and screenshot, save to test_data/{domain}/sample_{timestamp}/.

        Args:
            url: URL to fetch
            domain: Domain name (auto-detected from URL if not provided)
            quiet: Suppress verbose output

        Returns:
            Path to sample directory

        Raises:
            PlaywrightTimeoutError: If page load times out
            Exception: For other errors during fetch
        """
        # Auto-detect domain from URL
        if not domain:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')

        # Normalize domain for filename (replace dots with underscores)
        domain_dir = domain.replace('.', '_')

        # Create timestamp-based sample directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sample_dir = self.base_dir / domain_dir / f"sample_{timestamp}"
        sample_dir.mkdir(parents=True, exist_ok=True)

        if not quiet:
            print(f"Fetching: {url}")
            print(f"Saving to: {sample_dir}")

        # Fetch with Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=STEALTH_ARGS)

            try:
                context = await browser.new_context(**get_stealth_context_options())
                page = await context.new_page()
                await apply_stealth(page)

                # Navigate to page
                start_time = datetime.now()
                await page.goto(url, wait_until='load', timeout=60000)

                # Wait for dynamic content to load
                await page.wait_for_timeout(2000)

                # Try to handle cookie consent dialogs
                await handle_cookie_dialog(page, quiet)

                # Calculate fetch duration
                fetch_duration = (datetime.now() - start_time).total_seconds()

                # Get page title
                page_title = await page.title()

                # Get HTML
                html = await page.content()
                html_path = sample_dir / "page.html"
                html_path.write_text(html, encoding='utf-8')

                if not quiet:
                    print(f"✓ HTML saved ({len(html):,} bytes)")

                # Get screenshot
                screenshot_bytes = await page.screenshot(full_page=True, type='png')
                screenshot_path = sample_dir / "page.png"
                screenshot_path.write_bytes(screenshot_bytes)

                if not quiet:
                    print(f"✓ Screenshot saved ({len(screenshot_bytes):,} bytes)")

            finally:
                await browser.close()

        # Save metadata
        metadata = {
            "url": url,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "page_title": page_title,
            "html_size": len(html),
            "screenshot_size": len(screenshot_bytes),
            "fetch_duration_seconds": round(fetch_duration, 2),
        }

        metadata_path = sample_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

        if not quiet:
            print(f"✓ Metadata saved")
            print(f"\nSample ready: {sample_dir}")

        return sample_dir

    def list_samples(self, domain: str) -> list[Path]:
        """
        List all samples for a domain.

        Args:
            domain: Domain name

        Returns:
            List of sample directory paths, sorted by timestamp (newest first)
        """
        domain_dir = domain.replace('.', '_')
        test_data_path = self.base_dir / domain_dir

        if not test_data_path.exists():
            return []

        samples = sorted(
            test_data_path.glob("sample_*"),
            key=lambda p: p.name,
            reverse=True
        )

        return samples

    def get_latest_sample(self, domain: str) -> Path | None:
        """
        Get the most recent sample for a domain.

        Args:
            domain: Domain name

        Returns:
            Path to latest sample directory, or None if no samples exist
        """
        samples = self.list_samples(domain)
        return samples[0] if samples else None


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch web page and capture HTML + screenshot for extractor development',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s https://www.komplett.no/product/1310167
  %(prog)s https://example.com --domain example.com
  %(prog)s https://example.com --quiet
        '''
    )

    parser.add_argument(
        'url',
        help='URL to fetch and capture'
    )

    parser.add_argument(
        '--domain',
        help='Domain name (auto-detected from URL if not provided)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force refetch even if recent sample exists (currently not implemented)'
    )

    args = parser.parse_args()

    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://", file=sys.stderr)
        sys.exit(1)

    try:
        fetcher = SampleFetcher()
        sample_dir = asyncio.run(
            fetcher.fetch_sample(args.url, args.domain, args.quiet)
        )

        # Output sample directory path for easy parsing by subprocess callers
        if args.quiet:
            print(str(sample_dir))

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
