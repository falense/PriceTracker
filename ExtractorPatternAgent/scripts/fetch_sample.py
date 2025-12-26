#!/usr/bin/env python3
"""
Fetch web page sample (HTML + screenshot) for extractor development.

Usage:
    python scripts/fetch_sample.py https://www.komplett.no/product/1310167
    python scripts/fetch_sample.py <url> --domain komplett.no
    python scripts/fetch_sample.py <url> --quiet
    python scripts/fetch_sample.py <url> --no-headless  # For sites with strong bot detection
"""

import asyncio
import sys
import argparse
import json
import random
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

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
        'button:has-text("Godta alle")',  # Norwegian: Accept all
        'button:has-text("Godkjenn")',  # Norwegian: Approve
        'button:has-text("Aksepter")',  # Norwegian: Accept
        '[id*="accept"][id*="cookie"]',
        '[id*="consent"][id*="accept"]',
        '[class*="accept"][class*="cookie"]',
        '[class*="consent"][class*="accept"]',
        # CookieInformation (used by many Norwegian sites)
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        "#CybotCookiebotDialogBodyButtonAccept",
        'a[id*="CybotCookiebotDialogBodyLevelButtonAccept"]',
        '.CookieInformation button[data-action="accept"]',
        # OneTrust
        "#onetrust-accept-btn-handler",
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

    # Fallback: role-based click for common labels
    try:
        accept_button = page.get_by_role("button", name="Godta alle")
        if await accept_button.is_visible():
            await accept_button.click()
            if not quiet:
                print("✓ Cookie dialog accepted (role fallback)")
            await page.wait_for_timeout(1000)
            return
    except:
        pass

    # Fallback: check iframe-based dialogs
    for frame in page.frames:
        try:
            accept_button = frame.get_by_role("button", name="Godta alle")
            if await accept_button.is_visible():
                await accept_button.click()
                if not quiet:
                    print("✓ Cookie dialog accepted (iframe role fallback)")
                await page.wait_for_timeout(1000)
                return
        except:
            continue


async def simulate_human_behavior(page, quiet: bool = False):
    """
    Simulate human-like behavior to avoid bot detection.
    
    - Random mouse movements
    - Scrolling behavior
    - Natural timing delays
    
    Args:
        page: Playwright page object
        quiet: Suppress output
    """
    try:
        # Random small mouse movements
        viewport = page.viewport_size
        if viewport:
            for _ in range(3):
                x = random.randint(100, viewport['width'] - 100)
                y = random.randint(100, viewport['height'] - 100)
                await page.mouse.move(x, y)
                await page.wait_for_timeout(random.randint(100, 300))
        
        # Simulate scrolling behavior
        await page.evaluate("""
            () => {
                window.scrollTo({
                    top: Math.random() * 500,
                    behavior: 'smooth'
                });
            }
        """)
        await page.wait_for_timeout(random.randint(500, 1000))
        
        # Scroll back up
        await page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
        await page.wait_for_timeout(random.randint(300, 600))
        
        if not quiet:
            print("✓ Human behavior simulated")
            
    except Exception as e:
        # Non-critical, continue even if simulation fails
        if not quiet:
            print(f"⚠ Human behavior simulation failed: {e}")


async def check_for_captcha(page, quiet: bool = False):
    """
    Check if page contains a CAPTCHA or bot detection.
    
    Returns:
        bool: True if CAPTCHA detected, False otherwise
    """
    captcha_indicators = [
        "captcha",
        "robot",
        "unusual traffic",
        "verify you are human",
        "security check",
        "punish",  # AliExpress uses this
        "slider verification",
    ]
    
    try:
        page_content = await page.content()
        page_text = (await page.inner_text("body")).lower()
        
        for indicator in captcha_indicators:
            if indicator in page_text.lower() or indicator in page_content.lower():
                if not quiet:
                    print(f"⚠ CAPTCHA/bot detection detected ('{indicator}' found)")
                return True
        
        # Check page title
        title = await page.title()
        if any(indicator in title.lower() for indicator in captcha_indicators):
            if not quiet:
                print(f"⚠ CAPTCHA/bot detection in title: {title}")
            return True
            
    except Exception as e:
        if not quiet:
            print(f"⚠ Error checking for CAPTCHA: {e}")
    
    return False


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
        self, url: str, domain: str = None, quiet: bool = False, headless: bool = True
    ) -> Path:
        """
        Fetch HTML and screenshot, save to test_data/{domain}/sample_{timestamp}/.

        Args:
            url: URL to fetch
            domain: Domain name (auto-detected from URL if not provided)
            quiet: Suppress verbose output
            headless: Run browser in headless mode (default: True)
                     Set to False for sites with strong bot detection

        Returns:
            Path to sample directory

        Raises:
            PlaywrightTimeoutError: If page load times out
            Exception: For other errors during fetch
        """
        # Auto-detect domain from URL
        if not domain:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")

        # Normalize domain for filename (replace dots with underscores)
        domain_dir = domain.replace(".", "_")

        # Create timestamp-based sample directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sample_dir = self.base_dir / domain_dir / f"sample_{timestamp}"
        sample_dir.mkdir(parents=True, exist_ok=True)

        if not quiet:
            print(f"Fetching: {url}")
            print(f"Saving to: {sample_dir}")
            if not headless:
                print("⚠ Running in non-headless mode (visible browser)")

        # Fetch with Playwright
        async with async_playwright() as p:
            # Launch browser with stealth args
            browser = await p.chromium.launch(
                headless=headless,
                args=STEALTH_ARGS
            )

            try:
                context = await browser.new_context(**get_stealth_context_options())
                page = await context.new_page()
                await apply_stealth(page)

                # Add random initial delay to appear more human-like
                await page.wait_for_timeout(random.randint(500, 1500))

                # Navigate to page with longer timeout for slow sites
                start_time = datetime.now()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=90000)
                except PlaywrightTimeoutError:
                    if not quiet:
                        print("⚠ Page load timeout, continuing anyway...")

                # Wait for dynamic content with random delay
                await page.wait_for_timeout(random.randint(3000, 5000))

                # Simulate human behavior (mouse movement, scrolling)
                await simulate_human_behavior(page, quiet)

                # Try to handle cookie consent dialogs
                await handle_cookie_dialog(page, quiet)

                # Additional wait after cookie dialog
                await page.wait_for_timeout(random.randint(1000, 2000))

                # Check for CAPTCHA
                has_captcha = await check_for_captcha(page, quiet)
                if has_captcha and not headless:
                    if not quiet:
                        print("⚠ CAPTCHA detected! Waiting 30 seconds for manual solving...")
                        print("  Please solve the CAPTCHA in the browser window.")
                    await page.wait_for_timeout(30000)  # Wait 30 seconds
                    
                    # Re-check after waiting
                    has_captcha = await check_for_captcha(page, quiet)
                    if has_captcha and not quiet:
                        print("⚠ CAPTCHA still present after waiting")

                # Wait for network to be idle
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    pass  # Non-critical

                # Calculate fetch duration
                fetch_duration = (datetime.now() - start_time).total_seconds()

                # Get page title
                page_title = await page.title()

                # Get HTML
                html = await page.content()
                html_path = sample_dir / "page.html"
                html_path.write_text(html, encoding="utf-8")

                if not quiet:
                    print(f"✓ HTML saved ({len(html):,} bytes)")

                # Get screenshot
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
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
            "headless": headless,
            "captcha_detected": has_captcha,
        }

        metadata_path = sample_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

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
        domain_dir = domain.replace(".", "_")
        test_data_path = self.base_dir / domain_dir

        if not test_data_path.exists():
            return []

        samples = sorted(
            test_data_path.glob("sample_*"), key=lambda p: p.name, reverse=True
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
        description="Fetch web page and capture HTML + screenshot for extractor development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://www.komplett.no/product/1310167
  %(prog)s https://example.com --domain example.com
  %(prog)s https://example.com --quiet
  %(prog)s https://www.aliexpress.com/item/123456.html --no-headless
        """,
    )

    parser.add_argument("url", help="URL to fetch and capture")

    parser.add_argument(
        "--domain", help="Domain name (auto-detected from URL if not provided)"
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress verbose output"
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (recommended for sites with strong bot detection like AliExpress)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refetch even if recent sample exists (currently not implemented)",
    )

    args = parser.parse_args()

    # Validate URL
    if not args.url.startswith(("http://", "https://")):
        print("Error: URL must start with http:// or https://", file=sys.stderr)
        sys.exit(1)

    try:
        fetcher = SampleFetcher()
        sample_dir = asyncio.run(
            fetcher.fetch_sample(
                args.url, 
                args.domain, 
                args.quiet,
                headless=not args.no_headless
            )
        )

        # Output sample directory path for easy parsing by subprocess callers
        if args.quiet:
            print(str(sample_dir))

        sys.exit(0)

    except PlaywrightTimeoutError:
        print("Error: Page load timeout (90s)", file=sys.stderr)
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
