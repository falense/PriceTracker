"""Browser tools for fetching and rendering web pages with comprehensive stealth."""

from claude_agent_sdk import tool
from playwright.async_api import async_playwright
from typing import Any, Dict
import logging
from ..utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options

logger = logging.getLogger(__name__)


@tool(
    "fetch_page",
    "Fetch HTML from a URL using headless browser. Returns page HTML content.",
    {"url": str, "wait_for_js": bool}
)
async def fetch_page_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch page HTML with Playwright using comprehensive stealth to avoid bot detection.

    Args:
        url: The URL to fetch
        wait_for_js: Whether to wait for JavaScript to finish (default: True)

    Returns:
        Dictionary with content containing the HTML
    """
    url = args["url"]
    wait_for_js = args.get("wait_for_js", True)

    logger.info(f"Fetching page: {url} (wait_for_js={wait_for_js})")

    try:
        async with async_playwright() as p:
            # Launch in headless mode with comprehensive stealth
            browser = await p.chromium.launch(
                headless=True,  # Required for Docker/server environments
                args=STEALTH_ARGS
            )

            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            # Create page and apply stealth
            page = await context.new_page()
            await apply_stealth(page)

            try:
                # Navigate to page - use 'load' instead of 'networkidle' to be less strict
                wait_until = "load" if wait_for_js else "domcontentloaded"
                await page.goto(url, wait_until=wait_until, timeout=60000)

                # Get final HTML
                html = await page.content()

                logger.info(f"Successfully fetched page. HTML length: {len(html)}")

                return {
                    "content": [{
                        "type": "text",
                        "text": f"Successfully fetched page from {url}\n\nHTML length: {len(html)} characters\n\n{html[:10000]}"
                    }]
                }
            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"Error fetching page {url}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching page: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "render_js",
    "Render JavaScript-heavy page and extract final HTML. Optionally wait for specific selector.",
    {"url": str, "wait_selector": str}
)
async def render_js_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render JS and wait for specific selector with comprehensive stealth.

    Args:
        url: The URL to render
        wait_selector: Optional CSS selector to wait for before capturing HTML

    Returns:
        Dictionary with content containing the rendered HTML
    """
    url = args["url"]
    wait_selector = args.get("wait_selector")

    logger.info(f"Rendering JS page: {url} (wait_selector={wait_selector})")

    try:
        async with async_playwright() as p:
            # Launch in headless mode with comprehensive stealth
            browser = await p.chromium.launch(
                headless=True,  # Required for Docker/server environments
                args=STEALTH_ARGS
            )

            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            # Create page and apply stealth
            page = await context.new_page()
            await apply_stealth(page)

            try:
                # Navigate and wait for load
                await page.goto(url, wait_until="load", timeout=60000)

                # Wait for specific selector if provided
                if wait_selector:
                    logger.info(f"Waiting for selector: {wait_selector}")
                    await page.wait_for_selector(wait_selector, timeout=10000)

                # Get final rendered HTML
                html = await page.content()

                logger.info(f"Successfully rendered page. HTML length: {len(html)}")

                return {
                    "content": [{
                        "type": "text",
                        "text": f"Successfully rendered JS page from {url}\n\nHTML length: {len(html)} characters\n\n{html[:10000]}"
                    }]
                }
            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"Error rendering JS page {url}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error rendering JS page: {str(e)}"
            }],
            "isError": True
        }


@tool(
    "screenshot_page",
    "Take a screenshot of a web page for visual analysis",
    {"url": str, "full_page": bool}
)
async def screenshot_page_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Take a screenshot of a web page with comprehensive stealth.

    Args:
        url: The URL to screenshot
        full_page: Whether to capture full page or just viewport (default: False)

    Returns:
        Dictionary with image content
    """
    url = args["url"]
    full_page = args.get("full_page", False)

    logger.info(f"Taking screenshot: {url} (full_page={full_page})")

    try:
        async with async_playwright() as p:
            # Launch in headless mode with comprehensive stealth
            browser = await p.chromium.launch(
                headless=True,  # Required for Docker/server environments
                args=STEALTH_ARGS
            )

            # Create context with stealth options
            context_options = get_stealth_context_options()
            context = await browser.new_context(**context_options)

            # Create page and apply stealth
            page = await context.new_page()
            await apply_stealth(page)

            try:
                await page.goto(url, wait_until="load", timeout=60000)

                # Take screenshot
                screenshot_bytes = await page.screenshot(full_page=full_page, type="png")

                logger.info(f"Screenshot captured successfully ({len(screenshot_bytes)} bytes)")

                # Encode as base64 string
                import base64
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

                return {
                    "content": [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64
                        }
                    }]
                }
            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"Error taking screenshot {url}: {e}")
        return {
            "content": [{
                "type": "text",
                "text": f"Error taking screenshot: {str(e)}"
            }],
            "isError": True
        }
