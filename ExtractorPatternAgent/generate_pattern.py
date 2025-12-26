#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "claude-agent-sdk",
# ]
# ///
"""
Autonomous extractor pattern generator using Claude Agent SDK.

Usage:
    uv run generate_pattern.py <url>

Example:
    uv run generate_pattern.py https://www.komplett.no/product/1310167

This script uses the Claude Agent SDK to autonomously:
1. Fetch HTML samples from the target URL
2. Validate that the sample is not blocked (CAPTCHA, 403, etc.)
3. Analyze HTML structure for extraction points
4. Generate a Python extractor module
5. Test the extractor against the sample
6. Iterate on failures until tests pass
7. Commit the result to git
"""

import asyncio
import sys
import re
from pathlib import Path
from urllib.parse import urlparse

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    CLINotFoundError,
    ProcessError,
)


def extract_domain(url: str) -> str:
    """
    Extract normalized domain from URL.

    Args:
        url: URL to extract domain from

    Returns:
        Normalized domain name

    Examples:
        'https://www.komplett.no/product/123' → 'komplett.no'
        'power.no:8080' → 'power.no'
        'www.example.com' → 'example.com'
    """
    # Handle URLs without scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    domain = domain.lower()

    # Remove www. prefix
    domain = re.sub(r'^www\.', '', domain)

    # Remove port
    domain = re.sub(r':\d+$', '', domain)

    return domain


def domain_to_filename(domain: str) -> str:
    """
    Convert domain to Python module filename.

    Args:
        domain: Domain name (e.g., 'komplett.no')

    Returns:
        Python module name (e.g., 'komplett_no')
    """
    return domain.replace('.', '_').replace('-', '_')


def check_extractor_exists(domain: str, base_dir: Path) -> bool:
    """
    Check if extractor already exists for the domain.

    Args:
        domain: Domain name
        base_dir: ExtractorPatternAgent directory

    Returns:
        True if extractor exists, False otherwise
    """
    module_name = domain_to_filename(domain)
    extractor_path = base_dir / "generated_extractors" / f"{module_name}.py"
    return extractor_path.exists()


def load_pattern_guide(base_dir: Path) -> str:
    """
    Load the pattern creation guide from PATTERN_CREATION_GUIDE.md.

    Args:
        base_dir: ExtractorPatternAgent directory

    Returns:
        Full content of the pattern creation guide
    """
    guide_path = base_dir / "PATTERN_CREATION_GUIDE.md"
    return guide_path.read_text(encoding='utf-8')


def build_system_prompt(guide_content: str) -> dict:
    """
    Build system prompt with Claude Code preset + pattern creation guide.

    Args:
        guide_content: Content from PATTERN_CREATION_GUIDE.md

    Returns:
        System prompt configuration dict
    """
    return {
        "type": "preset",
        "preset": "claude_code",
        "append": f"""

## SPECIAL INSTRUCTIONS: Extractor Pattern Generation

You are creating a Python web scraping extractor following this comprehensive guide:

{guide_content}

CRITICAL REQUIREMENTS:
1. **Fail Fast on Blocking**: If CAPTCHA/403/blocking detected, STOP IMMEDIATELY and report
2. **Follow 7-Step Workflow**: Fetch → Validate → Analyze → Generate → Test → Iterate → Commit
3. **Use Existing Tools**: `uv run scripts/fetch_sample.py` and `test_extractor.py`
4. **Generate Complete Extractor**: PATTERN_METADATA + 7 extract_* functions
5. **Iterate on Test Failures**: Analyze, update selectors, re-test until passing
6. **Auto-Commit Result**: `git add` and `git commit` the final extractor

Working directory: ExtractorPatternAgent/
"""
    }


def build_agent_options(base_dir: Path) -> ClaudeAgentOptions:
    """
    Configure Claude Agent SDK for extractor generation.

    Args:
        base_dir: ExtractorPatternAgent directory

    Returns:
        Configured ClaudeAgentOptions
    """
    guide_content = load_pattern_guide(base_dir)

    return ClaudeAgentOptions(
        # All paths relative to this directory
        cwd=str(base_dir.absolute()),

        # System prompt with injected guide
        system_prompt=build_system_prompt(guide_content),

        # Allow necessary tools only
        allowed_tools=[
            "Read",      # Read HTML samples, existing extractors
            "Write",     # Create new extractor file
            "Edit",      # Modify extractor during iteration
            "Bash",      # Run fetch_sample.py, test_extractor.py, git
            "Glob",      # Find test data directories
            "Grep",      # Search HTML for patterns
        ],

        # Auto-approve all file edits (full automation)
        permission_mode="acceptEdits",

        # Budget for iteration (fetch, analyze, generate, test, fix, re-test)
        max_turns=50,

        # No external settings (pure programmatic config)
        setting_sources=None,
    )


def build_task_prompt(url: str, domain: str) -> str:
    """
    Build comprehensive task prompt with explicit 7-step workflow.

    Args:
        url: Target URL to create extractor for
        domain: Extracted domain name

    Returns:
        Complete task prompt for Claude
    """
    module_name = domain_to_filename(domain)

    return f"""Create a new Python extractor for {domain} from: {url}

Follow this exact 7-step workflow:

## Step 1: Fetch Sample Data

Run: `uv run scripts/fetch_sample.py {url}`

Creates:
- `test_data/{module_name}/sample_<timestamp>/page.html` - Full HTML
- `test_data/{module_name}/sample_<timestamp>/page.png` - Screenshot
- `test_data/{module_name}/sample_<timestamp>/metadata.json` - Metadata

## Step 2: CRITICAL - Validate Sample (FAIL FAST!)

**Before proceeding, you MUST verify:**

1. View screenshot: `test_data/{module_name}/sample_<timestamp>/page.png`
   - Check for CAPTCHA, login walls, error pages
   - Verify product page is visible

2. Read HTML: `test_data/{module_name}/sample_<timestamp>/page.html`
   - Verify it contains actual product data
   - Not an error/block page

**If ANY blocking detected:**
- STOP IMMEDIATELY
- Report: "Cannot fetch valid test data from {domain}. Site blocking: [CAPTCHA/403/login]"
- EXIT the task (do not create extractor)

## Step 3: Analyze HTML Structure

Identify extraction targets using this priority:

1. **JSON-LD (Schema.org)** - confidence 0.95 ⭐ PREFERRED
   - Look for: `<script type="application/ld+json">` with `@type: "Product"`
   - Extract: name, offers.price, offers.priceCurrency, image, sku

2. **OpenGraph meta tags** - confidence 0.95
   - `og:title`, `og:image`, `og:price:amount`, `og:price:currency`

3. **Data attributes** - confidence 0.90
   - `[data-price]`, `[data-product-id]`, `[itemprop="sku"]`

4. **Semantic CSS** - confidence 0.80
   - `.product-price`, `.product-title`, `.stock-status`

5. **Generic CSS** - confidence 0.70 (last resort)
   - `h1`, `.price`, etc.

Fields to extract (7 total):
- **price** (REQUIRED)
- **title** (REQUIRED)
- **currency** (REQUIRED)
- **image** (IMPORTANT)
- **availability** (IMPORTANT)
- **article_number** (OPTIONAL)
- **model_number** (OPTIONAL)

## Step 4: Generate Extractor

Create file: `generated_extractors/{module_name}.py`

**Required structure:**

```python
\"\"\"Extractor for {domain}\"\"\"
import re
import json
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor

PATTERN_METADATA = {{
    'domain': '{domain}',
    'generated_at': '<ISO timestamp>',
    'generator': 'autonomous-agent',
    'version': '1.0',
    'confidence': 0.90,  # Based on extraction method
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number', 'currency'],
    'notes': 'Initial pattern'
}}

def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    \"\"\"Extract price with 2-3 fallbacks.\"\"\"
    # PRIMARY: Best method (JSON-LD, data attr, etc.)
    # FALLBACK 1: Second-best
    # FALLBACK 2: Last resort
    return None

def extract_title(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract product title.\"\"\"
    # PRIMARY + fallbacks
    return None

def extract_image(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract primary product image URL.\"\"\"
    # PRIMARY + fallbacks
    return None

def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract stock availability status.\"\"\"
    # PRIMARY + fallbacks
    return None

def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract store article number (SKU).\"\"\"
    # PRIMARY + fallbacks
    return None

def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract manufacturer model/part number.\"\"\"
    # PRIMARY + fallbacks
    return None

def extract_currency(soup: BeautifulSoup) -> Optional[str]:
    \"\"\"Extract currency code.\"\"\"
    # PRIMARY + fallbacks
    return None
```

**Critical requirements:**
- Use `BaseExtractor.clean_price()` for price cleaning
- Use `BaseExtractor.clean_text()` for text normalization
- Provide 2-3 fallback methods per critical field
- Document extraction method in docstrings

## Step 5: Test Extractor

Run: `uv run scripts/test_extractor.py {domain}`

**Expected output:**
```
Testing: {domain}
Sample: sample_<timestamp>
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Field          ┃ Status    ┃ Extracted      ┃
┣━━━━━━━━━━━━━━━━╋━━━━━━━━━━━╋━━━━━━━━━━━━━━━━┫
│ price          │ ✓ PASS    │ 299            │
│ title          │ ✓ PASS    │ Product Name   │
│ currency       │ ✓ PASS    │ NOK            │
│ ...            │ ...       │ ...            │
└────────────────┴───────────┴────────────────┘

Summary: X/7 fields extracted (XX%)
Critical fields: ✓ Price, ✓ Title, ✓ Currency
```

## Step 6: Iterate Until Passing

**If tests fail:**

1. Read HTML around failed selectors
2. Identify alternative extraction methods:
   - Different CSS selectors
   - JSON data in other attributes
   - Fallback to meta tags
3. Update extractor with new methods (use Edit tool)
4. Re-test: `uv run scripts/test_extractor.py {domain}`
5. Repeat until critical fields pass

**Success criteria:**
- EXCELLENT: 7/7 fields (100%)
- GOOD: 5+/7 including all critical
- MINIMUM: 3/3 critical (price, title, currency)

**Iteration limit**: Max 5 test cycles. If still failing after 5, report best effort.

## Step 7: Commit to Git

Once tests pass minimum criteria:

```bash
git add generated_extractors/{module_name}.py
git commit -m "feat: Create extraction pattern for {domain} products"
```

**If commit fails**: Report error but don't fail task (extractor still works).

---

## Success Criteria

✅ Valid test data fetched and validated (no CAPTCHA/block)
✅ Extractor file created with complete structure
✅ Tests passing (minimum: price, title, currency)
✅ Git commit attempted
✅ Exit with success status

## Failure Scenarios

❌ CAPTCHA/403 blocking → Report and EXIT immediately (no extractor created)
❌ Cannot extract critical fields after 5 iterations → Report best effort
❌ Sample fetch timeout → Report network issue

**BEGIN WORKFLOW NOW!**
"""


async def generate_extractor(url: str, base_dir: Path) -> int:
    """
    Generate extractor using Claude Agent SDK.

    Args:
        url: Target URL to create extractor for
        base_dir: ExtractorPatternAgent directory

    Returns:
        Exit code: 0 on success, 1 on failure
    """
    domain = extract_domain(url)

    # Pre-flight: Check if extractor exists
    if check_extractor_exists(domain, base_dir):
        response = input(f"⚠️  Extractor for {domain} exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Aborted by user")
            return 1

    print(f"🚀 Starting autonomous generation for: {domain}")
    print(f"📍 URL: {url}")
    print(f"📂 Working dir: {base_dir}")
    print()

    options = build_agent_options(base_dir)
    prompt = build_task_prompt(url, domain)

    # State tracking
    blocking_detected = False
    extractor_created = False
    git_committed = False
    turn_count = 0
    final_result = None

    try:
        async for message in query(prompt=prompt, options=options):
            # Handle assistant messages (reasoning + tool use)
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        # Display Claude's thinking (truncated)
                        text = block.text
                        if len(text) > 200:
                            print(f"💭 {text[:200]}...")
                        else:
                            print(f"💭 {text}")

                        # Detect ACTUAL blocking (not just mentions)
                        # Look for phrases that indicate blocking was FOUND, not just checked
                        text_lower = text.lower()
                        blocking_phrases = [
                            'cannot fetch valid test data',
                            'site is blocking',
                            'appears to be blocking',
                            'detected captcha',
                            'page shows captcha',
                            'access is blocked',
                            'cannot complete pattern creation',
                            'cannot proceed',
                        ]
                        if any(phrase in text_lower for phrase in blocking_phrases):
                            blocking_detected = True
                            print("⚠️  BLOCKING DETECTED")

                    elif isinstance(block, ToolUseBlock):
                        # Display tool usage
                        tool_icon = {
                            "Read": "📖",
                            "Write": "✍️",
                            "Edit": "✏️",
                            "Bash": "🔧",
                            "Glob": "🔍",
                            "Grep": "🔎"
                        }.get(block.name, "🔨")

                        print(f"{tool_icon} Tool: {block.name}")

                        # Track important operations
                        if block.name == "Write":
                            file_path = block.input.get("file_path", "")
                            if "generated_extractors" in file_path:
                                extractor_created = True
                                print(f"   └─ Creating: {Path(file_path).name}")

                        elif block.name == "Bash":
                            cmd = block.input.get("command", "")
                            if len(cmd) > 80:
                                print(f"   └─ {cmd[:80]}...")
                            else:
                                print(f"   └─ {cmd}")
                            if "git commit" in cmd:
                                git_committed = True

            # Handle result message (final outcome)
            elif isinstance(message, ResultMessage):
                turn_count = message.num_turns

                print()
                print("=" * 60)
                print(f"✅ Task completed: {message.subtype}")
                print(f"⏱️  Duration: {message.duration_ms / 1000:.1f}s")
                print(f"🔄 Turns: {turn_count}")
                if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
                    print(f"💰 Cost: ${message.total_cost_usd:.4f}")
                print("=" * 60)

                # Determine success/failure (don't return, just set result and break)
                if blocking_detected:
                    print("❌ FAILED: Site blocking detected (CAPTCHA/403/etc)")
                    print("   Cannot create extractor without valid test data.")
                    final_result = 1

                elif message.is_error:
                    print(f"❌ FAILED: {message.subtype}")
                    final_result = 1

                elif not extractor_created:
                    print("❌ FAILED: No extractor file was created")
                    final_result = 1

                else:
                    print(f"✅ SUCCESS! Extractor created for {domain}")
                    if git_committed:
                        print("   └─ Git commit: ✅")
                    else:
                        print("   └─ Git commit: ⚠️  (may have failed, check manually)")
                    final_result = 0

                # Break to allow generator to close properly
                break

    except CLINotFoundError:
        print("❌ Error: Claude Code CLI not found")
        print("   Install: npm install -g @anthropic-ai/claude-code")
        return 1

    except ProcessError as e:
        print(f"❌ Process error: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"   stderr: {e.stderr[:500]}")
        return 1

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user (Ctrl+C)")
        return 130  # Standard SIGINT exit code

    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Return the result after generator has closed properly
    if final_result is not None:
        return final_result
    else:
        # Should not reach here, but handle gracefully
        print("⚠️  Warning: Task completed without definitive result")
        return 1


def main() -> int:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: uv run generate_pattern.py <url>")
        print()
        print("Examples:")
        print("  uv run generate_pattern.py https://www.komplett.no/product/1310167")
        print("  uv run generate_pattern.py https://power.no/product/123")
        return 1

    url = sys.argv[1]

    # Validate URL format
    if not url.startswith(('http://', 'https://', 'www.')):
        print(f"❌ Error: Invalid URL format: {url}")
        print("   URL must start with http://, https://, or www.")
        return 1

    # Resolve base directory (ExtractorPatternAgent/)
    script_path = Path(__file__).resolve()
    base_dir = script_path.parent

    # Run async workflow
    return asyncio.run(generate_extractor(url, base_dir))


if __name__ == "__main__":
    sys.exit(main())
