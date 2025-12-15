# Implementation Plan: Standalone Page Fetch & Capture Script

## Overview

Create a new standalone script `fetch_and_capture.py` that fetches a web page using Playwright with stealth capabilities and outputs two artifacts:
1. Complete rendered HTML content
2. Screenshot of the rendered page

This script will serve as scaffolding for the agent-based pattern extraction approach.

## Design Goals

1. **Simple & Self-Explanatory**: Clear code, minimal dependencies, good documentation
2. **Follows Existing Patterns**: Consistent with existing scripts like `test_stealth.py` and `generate_pattern.py`
3. **Stealth-First**: Comprehensive bot detection avoidance
4. **Production-Ready**: Proper error handling, logging, and exit codes
5. **CLI-Friendly**: Easy to use from command line or subprocess

## File Location

```
ExtractorPatternAgent/fetch_and_capture.py
```

## Script Design

### 1. Header & Dependencies

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.40.0",
# ]
# ///
```

**Rationale**:
- Follows PEP 723 inline script metadata (same as `generate_pattern.py`)
- Minimal dependencies - only Playwright required
- Compatible with `uv run` for easy execution

### 2. Core Functionality

#### Function: `async def fetch_and_capture(url: str, output_dir: str) -> tuple[str, str]`

**Parameters**:
- `url`: Target URL to fetch
- `output_dir`: Directory to save artifacts (default: current directory)

**Returns**:
- Tuple of (html_path, screenshot_path)

**Process**:
1. Initialize Playwright with stealth configuration
2. Navigate to URL with proper wait conditions
3. Extract rendered HTML content
4. Capture full-page screenshot
5. Save both artifacts to files
6. Return file paths

**Implementation Details**:

```python
async def fetch_and_capture(url: str, output_dir: str = ".") -> tuple[str, str]:
    """
    Fetch a web page and capture both HTML and screenshot.

    Args:
        url: The URL to fetch
        output_dir: Directory to save output files

    Returns:
        Tuple of (html_file_path, screenshot_file_path)
    """
    # Stealth browser setup (following existing patterns)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=STEALTH_ARGS
        )

        context = await browser.new_context(**get_stealth_context_options())
        page = await context.new_page()
        await apply_stealth(page)

        try:
            # Navigate with proper waits
            await page.goto(url, wait_until='load', timeout=60000)
            await page.wait_for_timeout(2000)  # Wait for dynamic content

            # Extract HTML
            html = await page.content()

            # Capture screenshot (full page)
            screenshot_bytes = await page.screenshot(full_page=True, type='png')

            # Generate output filenames
            domain = urlparse(url).netloc.replace('www.', '')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            html_filename = f"{domain}_{timestamp}.html"
            screenshot_filename = f"{domain}_{timestamp}.png"

            html_path = Path(output_dir) / html_filename
            screenshot_path = Path(output_dir) / screenshot_filename

            # Save artifacts
            html_path.write_text(html, encoding='utf-8')
            screenshot_path.write_bytes(screenshot_bytes)

            return (str(html_path), str(screenshot_path))

        finally:
            await browser.close()
```

### 3. CLI Interface

**Arguments**:
- `url` (required): URL to fetch
- `--output-dir` / `-o` (optional): Output directory (default: current directory)
- `--quiet` / `-q` (optional): Suppress verbose output

**Example Usage**:
```bash
# Basic usage
python fetch_and_capture.py https://www.komplett.no/product/123

# With UV
uv run fetch_and_capture.py https://www.komplett.no/product/123

# Specify output directory
python fetch_and_capture.py https://example.com -o /tmp/captures

# Quiet mode
python fetch_and_capture.py https://example.com -q
```

**Output Format**:
```
Fetching: https://www.komplett.no/product/123
✓ Page loaded (2.3s)
✓ HTML captured (245,892 bytes)
✓ Screenshot captured (full page)

Artifacts saved:
  HTML:       komplett.no_20251215_143022.html
  Screenshot: komplett.no_20251215_143022.png
```

### 4. Output File Naming Convention

**Pattern**: `{domain}_{timestamp}.{extension}`

**Examples**:
- `komplett.no_20251215_143022.html`
- `komplett.no_20251215_143022.png`
- `amazon.com_20251215_143530.html`
- `amazon.com_20251215_143530.png`

**Rationale**:
- Domain helps identify the source at a glance
- Timestamp ensures uniqueness and chronological ordering
- Clear extension shows file type
- No special characters or spaces (filesystem-safe)

### 5. Error Handling

**Error Scenarios**:
1. **Invalid URL**: Exit with code 1, helpful error message
2. **Network timeout**: Exit with code 2, show timeout duration
3. **Bot detection**: Exit with code 3, suggest troubleshooting
4. **File write error**: Exit with code 4, show permission/disk issues
5. **Playwright not installed**: Exit with code 5, show install instructions

**Implementation**:
```python
try:
    html_path, screenshot_path = await fetch_and_capture(url, output_dir)
except PlaywrightTimeoutError:
    print("Error: Page load timeout (60s)")
    sys.exit(2)
except PermissionError as e:
    print(f"Error: Cannot write to output directory: {e}")
    sys.exit(4)
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
    sys.exit(1)
```

### 6. Progress Indicators

Use simple print statements (not Rich library for minimal dependencies):

```python
print(f"Fetching: {url}")
print("✓ Browser launched")
print("✓ Page loaded")
print(f"✓ HTML captured ({len(html):,} bytes)")
print("✓ Screenshot captured")
print(f"\nArtifacts saved:")
print(f"  HTML:       {html_filename}")
print(f"  Screenshot: {screenshot_filename}")
```

### 7. Stealth Integration

**Reuse Existing Components**:
```python
sys.path.insert(0, str(Path(__file__).parent / "src"))
from utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options
```

**Stealth Application Flow**:
1. Launch browser with `STEALTH_ARGS`
2. Create context with `get_stealth_context_options()`
3. Apply stealth script with `apply_stealth(page)`
4. Navigate with proper wait conditions
5. Wait additional 2000ms for dynamic content

## Implementation Structure

```python
#!/usr/bin/env python3
# [PEP 723 header]

"""
Fetch and capture web page artifacts for agent analysis.

This script fetches a web page using Playwright with comprehensive stealth
measures and saves two artifacts:
1. Complete rendered HTML
2. Full-page screenshot

Usage:
    python fetch_and_capture.py <url>
    python fetch_and_capture.py <url> -o /output/dir
"""

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from playwright.async_api import async_playwright

# Import stealth utilities
sys.path.insert(0, str(Path(__file__).parent / "src"))
from utils.stealth import STEALTH_ARGS, apply_stealth, get_stealth_context_options


async def fetch_and_capture(url: str, output_dir: str = ".") -> tuple[str, str]:
    """[Implementation as above]"""
    pass


def main():
    """CLI entry point"""
    # Parse arguments
    # Validate inputs
    # Run async function
    # Display results
    # Exit with appropriate code
    pass


if __name__ == "__main__":
    main()
```

## Testing Strategy

### Test Cases

1. **Basic Fetch**: Simple e-commerce page (komplett.no)
2. **Bot Detection**: High-security site (Amazon)
3. **JavaScript-Heavy**: SPA with dynamic content
4. **Output Directory**: Custom output path
5. **Invalid URL**: Error handling
6. **Network Timeout**: Slow/unreachable site

### Manual Testing Commands

```bash
# Test 1: Basic fetch
uv run fetch_and_capture.py https://www.komplett.no/product/1310167

# Test 2: Amazon (bot detection test)
uv run fetch_and_capture.py https://www.amazon.com/dp/B0F1P5N81H

# Test 3: Custom output directory
mkdir -p /tmp/test_captures
uv run fetch_and_capture.py https://www.proshop.no -o /tmp/test_captures

# Test 4: Invalid URL
uv run fetch_and_capture.py not-a-url

# Test 5: Verify artifacts
ls -lh *.html *.png
file *.png
head -n 20 *.html
```

## Integration with Agent Architecture

### How Agents Will Use This Script

```python
# In agent implementation
import subprocess

result = subprocess.run([
    'python',
    '/extractor/fetch_and_capture.py',
    url,
    '--output-dir', '/tmp/agent_workspace'
], capture_output=True, text=True)

if result.returncode == 0:
    # Parse output to get file paths
    lines = result.stdout.strip().split('\n')
    html_path = extract_path_from_line(lines, "HTML:")
    screenshot_path = extract_path_from_line(lines, "Screenshot:")

    # Agent can now:
    # 1. Read HTML for pattern extraction
    # 2. Analyze screenshot for visual validation
    # 3. Use Claude with vision to understand page structure
```

### Agent Workflow

```
1. User provides product URL
2. Agent calls fetch_and_capture.py → gets HTML + screenshot
3. Agent uses Claude SDK with:
   - HTML content (for structure analysis)
   - Screenshot (for visual context)
4. Claude analyzes both and generates extraction patterns
5. Agent validates patterns against the HTML
6. Agent returns refined extraction patterns
```

## Dependencies

### Python Packages

```txt
playwright>=1.40.0
```

### System Requirements

- Playwright browsers installed: `playwright install chromium`
- Python 3.12+
- Write permissions in output directory

## File Size Considerations

**Typical Output Sizes**:
- HTML: 100KB - 2MB (most e-commerce pages)
- Screenshot: 500KB - 5MB (full page PNG)

**Storage Management**:
- Script does not implement automatic cleanup
- Caller responsible for managing artifacts
- Timestamp-based naming allows easy sorting/cleanup

## Documentation

### Inline Documentation

- Module docstring with usage examples
- Function docstrings with Args/Returns
- Inline comments for complex logic
- Type hints for all functions

### README Updates

Add section to `ExtractorPatternAgent/README.md`:

```markdown
### Fetch and Capture Script

Standalone utility for fetching web pages and capturing artifacts:

\`\`\`bash
# Basic usage
uv run fetch_and_capture.py https://example.com/product/123

# With custom output directory
uv run fetch_and_capture.py https://example.com/product/123 -o ./captures
\`\`\`

Outputs:
- `{domain}_{timestamp}.html` - Full rendered HTML
- `{domain}_{timestamp}.png` - Full-page screenshot

This script is used by the agent-based pattern extraction system.
```

## Alternative Approaches Considered

### 1. Combined with generate_pattern.py

**Pros**: Single script for everything
**Cons**: Mixing concerns, harder to maintain, larger scope
**Decision**: Rejected - keep focused scripts

### 2. Use Rich library for output

**Pros**: Beautiful terminal output
**Cons**: Extra dependency, harder to parse from subprocess
**Decision**: Rejected - keep minimal dependencies

### 3. JSON output format

**Pros**: Machine-readable output
**Cons**: Less human-friendly, overkill for simple paths
**Decision**: Rejected - simple text output is sufficient

### 4. Base64 embed screenshot in HTML

**Pros**: Single artifact
**Cons**: Huge HTML file, harder to work with
**Decision**: Rejected - separate files are more practical

## Success Criteria

✓ Script can be run with `uv run fetch_and_capture.py <url>`
✓ Outputs valid HTML file with complete rendered content
✓ Outputs valid PNG screenshot of full page
✓ Works on major e-commerce sites (komplett.no, proshop.no)
✓ Bypasses common bot detection
✓ Clear error messages for common failures
✓ File naming is consistent and filesystem-safe
✓ Can be called from subprocess with predictable output
✓ Execution time under 10 seconds for typical pages

## Future Enhancements (Out of Scope)

- Wait for specific selectors before capture
- Multiple screenshot formats (JPEG, WebP)
- HTML simplification/cleanup options
- Automatic retry on timeout
- Progress bar for long-running fetches
- Parallel fetching of multiple URLs
- Output to stdout instead of files
- Configurable viewport sizes
- Mobile emulation mode

## Summary

This implementation provides a clean, focused utility script that:
1. Follows established patterns in the codebase
2. Provides essential functionality for agent-based extraction
3. Maintains simplicity and clarity
4. Integrates seamlessly with existing stealth infrastructure
5. Can be easily called from other scripts or agents

The script serves as the foundation for the next phase: building an agent that uses these artifacts to intelligently generate extraction patterns.
