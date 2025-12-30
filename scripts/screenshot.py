#!/usr/bin/env python3
"""
Take screenshots of web pages using Playwright for agent analysis.

This tool uses Playwright to capture screenshots that can be analyzed by agents.
It supports persistent browser sessions for authenticated screenshots.

Usage:
    # Basic screenshot
    python3 scripts/screenshot.py <url> [--output PATH]

    # Interactive login mode (opens visible browser)
    python3 scripts/screenshot.py --login <session_name> <url>

    # Use saved session
    python3 scripts/screenshot.py --session <session_name> <url>

    # List saved sessions
    python3 scripts/screenshot.py --list-sessions

Examples:
    # Take a basic screenshot
    python3 scripts/screenshot.py https://example.com

    # Login interactively and save session
    python3 scripts/screenshot.py --login mysite https://example.com/login

    # Use saved session for screenshot
    python3 scripts/screenshot.py --session mysite https://example.com/dashboard

    # Full page screenshot with session
    python3 scripts/screenshot.py --session mysite https://example.com --full-page
"""

import asyncio
import sys
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime


# Directory for storing browser sessions
SESSION_DIR = Path.home() / ".playwright_sessions"
SESSION_DIR.mkdir(exist_ok=True)

# Directory for storing screenshots (project-local, not version controlled)
PROJECT_DIR = Path(os.getenv("CLAUDE_PROJECT_DIR", "."))
SCREENSHOT_DIR = PROJECT_DIR / ".screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def get_session_path(session_name: str) -> Path:
    """Get the directory path for a named session."""
    return SESSION_DIR / session_name


def list_sessions():
    """List all saved browser sessions."""
    sessions = [d.name for d in SESSION_DIR.iterdir() if d.is_dir()]
    if not sessions:
        print("No saved sessions found.")
        return

    print("Saved browser sessions:")
    for session in sorted(sessions):
        session_path = get_session_path(session)
        # Check if session has cookies
        state_file = session_path / "state.json"
        if state_file.exists():
            modified = datetime.fromtimestamp(state_file.stat().st_mtime)
            print(f"  - {session} (last used: {modified.strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            print(f"  - {session}")


async def interactive_login(
    session_name: str,
    url: str,
    width: int = 1280,
    height: int = 720,
    timeout: int = 30000,
) -> None:
    """
    Open a visible browser for interactive login and save the session.

    Args:
        session_name: Name for the session
        url: URL to open for login
        width: Viewport width in pixels
        height: Viewport height in pixels
        timeout: Navigation timeout in milliseconds
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Error: Playwright not found. Install with: uv pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    session_path = get_session_path(session_name)
    session_path.mkdir(exist_ok=True)

    print(f"Opening browser for interactive login...")
    print(f"Session will be saved as: {session_name}")
    print(f"Browser will open at: {url}")
    print("\nInstructions:")
    print("1. Complete your login in the browser window")
    print("2. Navigate to any pages you need to be logged into")
    print("3. When done, close the browser window")
    print("\nWaiting for you to close the browser...")

    playwright = None
    browser = None
    context = None

    try:
        playwright = await async_playwright().start()

        # Launch visible browser for interactive login
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        # Create persistent context to save state
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Create page and navigate
        page = await context.new_page()
        await page.goto(url, wait_until="load", timeout=timeout)

        # Wait for user to close the browser
        await page.wait_for_event("close", timeout=0)  # Wait indefinitely

    except Exception as e:
        if "Target page, context or browser has been closed" not in str(e):
            print(f"Error during interactive login: {e}", file=sys.stderr)
            sys.exit(1)

    finally:
        # Save the session state before cleanup
        if context:
            try:
                state_file = session_path / "state.json"
                await context.storage_state(path=str(state_file))
                print(f"\n✓ Session saved successfully: {session_name}")
                print(f"  State file: {state_file}")
            except Exception as e:
                print(f"Warning: Could not save session state: {e}", file=sys.stderr)

        # Cleanup
        if context:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
            except Exception:
                pass
        if browser:
            try:
                await asyncio.wait_for(browser.close(), timeout=5.0)
            except Exception:
                pass
        if playwright:
            try:
                await asyncio.wait_for(playwright.stop(), timeout=5.0)
            except Exception:
                pass


async def take_screenshot(
    url: str,
    output_path: str | None = None,
    width: int = 1280,
    height: int = 720,
    full_page: bool = False,
    timeout: int = 30000,
    session_name: str | None = None,
) -> str:
    """
    Take a screenshot of a web page using Playwright.

    Args:
        url: The URL to screenshot
        output_path: Path to save screenshot (default: auto-generated in /tmp)
        width: Viewport width in pixels
        height: Viewport height in pixels
        full_page: Whether to capture the full scrollable page
        timeout: Navigation timeout in milliseconds
        session_name: Name of saved session to use (optional)

    Returns:
        Path to the saved screenshot
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "Error: Playwright not found. Install with: uv pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check if session exists
    storage_state = None
    if session_name:
        session_path = get_session_path(session_name)
        state_file = session_path / "state.json"
        if not state_file.exists():
            print(f"Error: Session '{session_name}' not found.", file=sys.stderr)
            print(f"Available sessions:", file=sys.stderr)
            list_sessions()
            sys.exit(1)
        storage_state = str(state_file)
        print(f"Using session: {session_name}")

    # Generate output path if not provided
    if output_path is None:
        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "_").replace(":", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_suffix = f"_{session_name}" if session_name else ""
        filename = f"screenshot_{domain}{session_suffix}_{timestamp}.png"
        output_path = str(SCREENSHOT_DIR / filename)

    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    playwright = None
    browser = None
    context = None
    page = None

    try:
        playwright = await async_playwright().start()

        # Launch browser
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        # Create context with optional storage state
        context_options = {
            "viewport": {"width": width, "height": height},
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        if storage_state:
            context_options["storage_state"] = storage_state

        context = await browser.new_context(**context_options)

        # Create page and navigate
        page = await context.new_page()
        await page.goto(url, wait_until="load", timeout=timeout)

        # Wait for dynamic content
        await asyncio.sleep(1)

        # Take screenshot
        await page.screenshot(path=str(output_file), full_page=full_page)

        print(f"Screenshot saved to: {output_file}")
        return str(output_file)

    except Exception as e:
        print(f"Error taking screenshot: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        # Cleanup
        if page:
            try:
                await asyncio.wait_for(page.close(), timeout=5.0)
            except Exception:
                pass
        if context:
            try:
                await asyncio.wait_for(context.close(), timeout=5.0)
            except Exception:
                pass
        if browser:
            try:
                await asyncio.wait_for(browser.close(), timeout=5.0)
            except Exception:
                pass
        if playwright:
            try:
                await asyncio.wait_for(playwright.stop(), timeout=5.0)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Take screenshots of web pages using Playwright with session support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic screenshot
  %(prog)s https://example.com

  # Interactive login (opens visible browser)
  %(prog)s --login mysite https://example.com/login

  # Screenshot with saved session
  %(prog)s --session mysite https://example.com/dashboard

  # Full page screenshot with session
  %(prog)s --session mysite https://example.com --full-page

  # List saved sessions
  %(prog)s --list-sessions
        """,
    )

    parser.add_argument("url", nargs="?", help="URL to screenshot")
    parser.add_argument(
        "--output", "-o", help="Output file path (default: auto-generated in /tmp)"
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Viewport width in pixels (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Viewport height in pixels (default: 720)"
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Capture full scrollable page instead of just viewport",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Navigation timeout in milliseconds (default: 30000)",
    )
    parser.add_argument(
        "--session",
        help="Use a saved browser session (for authenticated screenshots)",
    )
    parser.add_argument(
        "--login",
        metavar="SESSION_NAME",
        help="Interactive login mode: open visible browser to login and save session",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all saved browser sessions",
    )

    args = parser.parse_args()

    # Handle list sessions
    if args.list_sessions:
        list_sessions()
        return

    # Handle interactive login
    if args.login:
        if not args.url:
            print("Error: URL is required for login mode", file=sys.stderr)
            sys.exit(1)
        asyncio.run(
            interactive_login(
                session_name=args.login,
                url=args.url,
                width=args.width,
                height=args.height,
                timeout=args.timeout,
            )
        )
        return

    # Handle screenshot
    if not args.url:
        print("Error: URL is required", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    asyncio.run(
        take_screenshot(
            url=args.url,
            output_path=args.output,
            width=args.width,
            height=args.height,
            full_page=args.full_page,
            timeout=args.timeout,
            session_name=args.session,
        )
    )


if __name__ == "__main__":
    main()
