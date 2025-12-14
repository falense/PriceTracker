# ExtractorPatternAgent Implementation Status & Agent Starting Point

## Current State: 60% Complete

### ✅ What's Working

1. **Agent Class Skeleton** (src/agent.py:1)
   - Basic structure exists
   - Claude SDK integration framework
   - Async context manager pattern

2. **Project Structure**
   - Tools directory created (src/tools/)
   - Models directory created (src/models/)
   - Utils directory created (src/utils/)
   - CLI interface exists (extractor-cli.py)

3. **Documentation**
   - Comprehensive ARCHITECTURE.md
   - README with usage examples
   - Tool specifications defined

### 🔴 Critical Missing Pieces

1. **Database Storage BROKEN** (CRITICAL)
   - Tools reference `patterns.db` (separate database)
   - Should use shared `../db.sqlite3` (Django database)
   - Should write to table `app_pattern`, not custom schema
   - Risk: Patterns saved but never found by PriceFetcher

2. **MCP Tools Implementation**
   - Tool files exist but may be incomplete
   - Need verification each tool works correctly
   - Browser tools require Playwright setup
   - Parser tools need testing with real HTML

3. **Agent System Prompt**
   - May need refinement based on testing
   - Extraction strategy needs validation
   - Output schema must match Pattern model

4. **Integration with WebUI**
   - No way for WebUI Celery tasks to call agent
   - Need subprocess or direct Python invocation
   - CLI interface must output parseable format

### ⚠️ Known Issues

1. **Pattern Output Format**: Unknown if agent output matches expected schema
2. **Validation Loop**: Pattern refinement based on feedback not tested
3. **Browser Dependencies**: Playwright browsers must be installed
4. **Error Handling**: Unknown how agent handles failed extractions

## Priority Tasks for Implementation Agent

### P0 - Blocking (Must Complete First)

#### Task 1: Fix Database Storage (CRITICAL)

**Problem**: Agent saves to wrong database in wrong format

**Current** (src/tools/storage.py - INCORRECT):
```python
DB_PATH = Path(__file__).parent.parent / "patterns.db"  # WRONG
```

**Required**: Point to shared Django database

**Solution A: Use Django ORM (RECOMMENDED)**

```python
# src/tools/storage.py
import os
import sys
from pathlib import Path

# Add Django project to path
DJANGO_PATH = Path(__file__).parent.parent.parent / "WebUI"
sys.path.insert(0, str(DJANGO_PATH))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

# Now can import Django models
from app.models import Pattern
from django.utils import timezone


async def save_pattern_tool(args: dict) -> dict:
    """Save extraction pattern to Django database."""
    domain = args["domain"]
    patterns = args["patterns"]

    try:
        # Use Django ORM
        pattern, created = Pattern.objects.update_or_create(
            domain=domain,
            defaults={
                'pattern_json': patterns,
                'last_validated': timezone.now()
            }
        )

        return {
            "content": [{
                "type": "text",
                "text": f"{'Created' if created else 'Updated'} pattern for {domain} (ID: {pattern.id})"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error saving pattern: {str(e)}"
            }],
            "isError": True
        }


async def load_pattern_tool(args: dict) -> dict:
    """Load pattern from Django database."""
    domain = args["domain"]

    try:
        pattern = Pattern.objects.get(domain=domain)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(pattern.pattern_json, indent=2)
            }]
        }
    except Pattern.DoesNotExist:
        return {
            "content": [{
                "type": "text",
                "text": f"No pattern found for {domain}"
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error loading pattern: {str(e)}"
            }],
            "isError": True
        }
```

**Solution B: Raw SQLite to Shared DB (ALTERNATIVE)**

If Django import causes issues:

```python
# src/tools/storage.py
import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime

def get_db_path():
    """Get path to shared Django database."""
    # Environment variable (preferred)
    db_path = os.getenv('DATABASE_PATH')
    if db_path:
        return db_path

    # Relative path fallback
    return str(Path(__file__).parent.parent.parent / "db.sqlite3")


async def save_pattern_tool(args: dict) -> dict:
    """Save pattern to Django database using raw SQL."""
    domain = args["domain"]
    patterns = args["patterns"]

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if pattern exists
        cursor.execute(
            "SELECT id FROM app_pattern WHERE domain = ?",
            (domain,)
        )
        existing = cursor.fetchone()

        now = datetime.utcnow().isoformat()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE app_pattern
                SET pattern_json = ?,
                    updated_at = ?,
                    last_validated = ?
                WHERE domain = ?
            """, (json.dumps(patterns), now, now, domain))
            action = "Updated"
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO app_pattern
                (domain, pattern_json, success_rate, total_attempts,
                 successful_attempts, created_at, updated_at, last_validated)
                VALUES (?, ?, 0.0, 0, 0, ?, ?, ?)
            """, (domain, json.dumps(patterns), now, now, now))
            action = "Created"

        conn.commit()
        conn.close()

        return {
            "content": [{
                "type": "text",
                "text": f"{action} pattern for {domain}"
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {str(e)}"
            }],
            "isError": True
        }
```

**Test**:
```python
# Test script: tests/test_storage_integration.py
import asyncio
import sys
import os

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ['DATABASE_PATH'] = '../db.sqlite3'

from tools.storage import save_pattern_tool, load_pattern_tool

async def test_storage():
    # Save pattern
    result = await save_pattern_tool({
        "domain": "test.example.com",
        "patterns": {
            "price": {
                "primary": {
                    "type": "css",
                    "selector": ".price",
                    "confidence": 0.9
                }
            }
        }
    })
    print("Save result:", result)

    # Load pattern
    result = await load_pattern_tool({
        "domain": "test.example.com"
    })
    print("Load result:", result)

asyncio.run(test_storage())
```

#### Task 2: Verify/Complete MCP Tools

**Files to Review**:
- `src/tools/browser.py` - Playwright browser tools
- `src/tools/parser.py` - HTML parsing tools
- `src/tools/validator.py` - Pattern validation tools
- `src/tools/storage.py` - Database tools (fix in Task 1)

**Checklist for Each Tool**:

1. **Browser Tools** (browser.py)

   Required tools:
   - `fetch_page` - Fetch HTML from URL
   - `render_js` - Render JavaScript-heavy pages

   Test:
   ```python
   from tools.browser import fetch_page_tool
   result = await fetch_page_tool({
       "url": "https://example.com",
       "wait_for_js": True
   })
   assert "content" in result
   assert len(result["content"][0]["text"]) > 0
   ```

2. **Parser Tools** (parser.py)

   Required tools:
   - `extract_structured_data` - Extract JSON-LD and meta tags
   - `analyze_selectors` - Suggest selector candidates

   Test:
   ```python
   html = """
   <html>
   <head>
       <script type="application/ld+json">
       {"@type": "Product", "offers": {"price": "29.99"}}
       </script>
   </head>
   <body>
       <span class="price">$29.99</span>
   </body>
   </html>
   """

   from tools.parser import extract_structured_data_tool
   result = await extract_structured_data_tool({"html": html})
   data = json.loads(result["content"][0]["text"])
   assert "jsonld" in data
   assert len(data["jsonld"]) > 0
   ```

3. **Validator Tools** (validator.py)

   Required tools:
   - `test_pattern` - Test selector against HTML
   - `validate_extraction` - Validate extracted data format

   Test:
   ```python
   from tools.validator import test_pattern_tool, validate_extraction_tool

   # Test pattern
   result = await test_pattern_tool({
       "html": '<span class="price">$29.99</span>',
       "selector": ".price",
       "selector_type": "css"
   })
   data = json.loads(result["content"][0]["text"])
   assert data["success"] == True
   assert "$29.99" in data["extracted_value"]

   # Validate extraction
   result = await validate_extraction_tool({
       "field": "price",
       "value": "$29.99"
   })
   data = json.loads(result["content"][0]["text"])
   assert data["valid"] == True
   ```

**Create Test Suite**: `tests/test_tools.py`

```python
import pytest
import asyncio
from pathlib import Path

# Test data
TEST_HTML = Path(__file__).parent / "fixtures" / "test_product.html"

@pytest.mark.asyncio
async def test_browser_tools():
    """Test browser tools work."""
    from src.tools.browser import fetch_page_tool

    result = await fetch_page_tool({
        "url": "https://example.com",
        "wait_for_js": False
    })

    assert "content" in result
    assert "text" in result["content"][0]
    assert len(result["content"][0]["text"]) > 100

@pytest.mark.asyncio
async def test_parser_tools():
    """Test parser tools extract data correctly."""
    from src.tools.parser import extract_structured_data_tool, analyze_selectors_tool

    html = TEST_HTML.read_text()

    # Extract structured data
    result = await extract_structured_data_tool({"html": html})
    # ... assertions

    # Analyze selectors
    result = await analyze_selectors_tool({
        "html": html,
        "field": "price"
    })
    # ... assertions

@pytest.mark.asyncio
async def test_validator_tools():
    """Test validator tools work correctly."""
    from src.tools.validator import test_pattern_tool, validate_extraction_tool

    # Test CSS selector
    result = await test_pattern_tool({
        "html": '<div class="price">$29.99</div>',
        "selector": ".price",
        "selector_type": "css"
    })
    data = json.loads(result["content"][0]["text"])
    assert data["success"] == True

    # Validate price format
    result = await validate_extraction_tool({
        "field": "price",
        "value": "$29.99"
    })
    data = json.loads(result["content"][0]["text"])
    assert data["valid"] == True

@pytest.mark.asyncio
async def test_storage_tools():
    """Test storage tools work with Django database."""
    from src.tools.storage import save_pattern_tool, load_pattern_tool

    test_domain = "test-tools.example.com"

    # Save
    result = await save_pattern_tool({
        "domain": test_domain,
        "patterns": {"price": {"primary": {"type": "css", "selector": ".price"}}}
    })
    assert "isError" not in result

    # Load
    result = await load_pattern_tool({"domain": test_domain})
    assert "isError" not in result

    # Cleanup
    import sys, os
    sys.path.insert(0, '../WebUI')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from app.models import Pattern
    Pattern.objects.filter(domain=test_domain).delete()
```

Run tests:
```bash
cd ExtractorPatternAgent
pytest tests/test_tools.py -v
```

#### Task 3: Complete Agent Implementation

**File**: `src/agent.py`

**Current Issues**:
- System prompt may need tuning
- Output schema must match Pattern model
- Error handling needs robustness

**Verify Agent Structure**:

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class ExtractorPatternAgent:
    def __init__(self, config: dict = None):
        self.config = config or self._default_config()

    async def __aenter__(self):
        """Setup agent session."""
        # Verify system prompt guides agent correctly
        system_prompt = self._get_system_prompt()

        # Setup MCP server with tools
        mcp_server = self._create_mcp_server()

        # Initialize Claude SDK client
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={"extractor": mcp_server},
            allowed_tools=self._get_allowed_tools(),
            max_turns=20,
            model="claude-sonnet-4-5-20250929"
        )

        self.client = ClaudeSDKClient(options)
        await self.client.connect()
        return self

    async def generate_patterns(self, url: str, save_to_db: bool = True) -> dict:
        """Generate extraction patterns for product URL."""
        prompt = f"""Generate extraction patterns for: {url}

Steps:
1. Fetch the page HTML
2. Extract JSON-LD structured data if available
3. Analyze HTML for reliable selectors
4. Generate patterns for: price, title, availability, image
5. Test each pattern to verify it extracts correctly
6. Return patterns with confidence scores

Prioritize in order:
- JSON-LD (confidence 0.95+)
- Meta tags (confidence 0.85+)
- Semantic CSS (confidence 0.80+)
- XPath fallback (confidence 0.70+)
"""

        await self.client.query(prompt)

        # Receive response
        result = None
        async for message in self.client.receive_response():
            if isinstance(message, ResultMessage):
                result = json.loads(message.result)
                break

        # Optionally save to database
        if save_to_db and result:
            domain = urlparse(url).netloc.replace('www.', '')
            from .tools.storage import save_pattern_tool
            await save_pattern_tool({
                "domain": domain,
                "patterns": result
            })

        return result
```

**Test Agent**:

```python
# tests/test_agent.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_agent_generates_patterns():
    """Test agent can generate patterns for a real product page."""
    from src.agent import ExtractorPatternAgent

    async with ExtractorPatternAgent() as agent:
        # Use a stable test page
        url = "https://www.example.com/product/test"

        patterns = await agent.generate_patterns(url, save_to_db=False)

        assert patterns is not None
        assert "patterns" in patterns
        assert "price" in patterns["patterns"]
        assert "primary" in patterns["patterns"]["price"]
        assert patterns["patterns"]["price"]["primary"]["confidence"] > 0.6
```

### P1 - High Priority

#### Task 4: Create Callable Interface for WebUI

**Problem**: WebUI Celery task needs to call agent

**Solution**: Create entry point that can be called via subprocess

**File**: `scripts/generate_pattern.py`

```python
#!/usr/bin/env python3
"""
Entry point for pattern generation.
Called by WebUI Celery tasks.

Usage:
    python generate_pattern.py <url> --domain <domain> [--output json]
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent import ExtractorPatternAgent


async def main():
    parser = argparse.ArgumentParser(description='Generate extraction pattern')
    parser.add_argument('url', help='Product URL to analyze')
    parser.add_argument('--domain', help='Domain name (e.g., amazon.com)')
    parser.add_argument('--output', choices=['json', 'text'], default='json')
    parser.add_argument('--no-save', action='store_true', help="Don't save to database")

    args = parser.parse_args()

    try:
        async with ExtractorPatternAgent() as agent:
            patterns = await agent.generate_patterns(
                args.url,
                save_to_db=not args.no_save
            )

            if args.output == 'json':
                print(json.dumps(patterns, indent=2))
            else:
                print(f"Generated patterns for {args.domain}")
                print(f"Confidence: {patterns.get('metadata', {}).get('confidence_score', 'N/A')}")

            sys.exit(0)

    except Exception as e:
        if args.output == 'json':
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
```

Make executable:
```bash
chmod +x scripts/generate_pattern.py
```

**Test from WebUI**:
```bash
cd WebUI
python -c "
import subprocess
result = subprocess.run(
    ['uv', 'run', '../ExtractorPatternAgent/scripts/generate_pattern.py',
     'https://example.com/product/123',
     '--domain', 'example.com'],
    capture_output=True,
    text=True
)
print(result.stdout)
"
```

#### Task 5: Update CLI Interface

**File**: `extractor-cli.py`

Ensure CLI works with new storage layer:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "claude-agent-sdk",
#     "playwright",
#     "beautifulsoup4",
#     "lxml",
#     "click",
#     "rich",
# ]
# ///

import asyncio
import click
from rich.console import Console
from rich.table import Table

console = Console()

@click.group()
def cli():
    """ExtractorPatternAgent CLI"""
    pass

@cli.command()
@click.argument('url')
@click.option('--domain', help='Domain name')
@click.option('--output', '-o', type=click.Path(), help='Save to file')
def generate(url, domain, output):
    """Generate extraction patterns for URL."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from agent import ExtractorPatternAgent
    import json

    async def run():
        async with ExtractorPatternAgent() as agent:
            console.print(f"[blue]Analyzing {url}...[/blue]")
            patterns = await agent.generate_patterns(url)

            if output:
                Path(output).write_text(json.dumps(patterns, indent=2))
                console.print(f"[green]✓ Saved to {output}[/green]")
            else:
                console.print_json(data=patterns)

            return patterns

    asyncio.run(run())

@cli.command()
@click.option('--domain', help='Filter by domain')
def list(domain):
    """List stored patterns."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "WebUI"))

    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()

    from app.models import Pattern

    patterns = Pattern.objects.all()
    if domain:
        patterns = patterns.filter(domain__icontains=domain)

    table = Table(title="Stored Patterns")
    table.add_column("Domain", style="cyan")
    table.add_column("Success Rate", style="green")
    table.add_column("Attempts", style="yellow")
    table.add_column("Last Validated", style="blue")

    for p in patterns:
        table.add_row(
            p.domain,
            f"{p.success_rate:.1%}",
            str(p.total_attempts),
            str(p.last_validated) if p.last_validated else "Never"
        )

    console.print(table)

if __name__ == '__main__':
    cli()
```

#### Task 6: Add Test Fixtures

**Location**: `tests/fixtures/`

Create sample HTML files for testing:

```bash
mkdir -p tests/fixtures
```

**File**: `tests/fixtures/amazon_product.html`
```html
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org/",
      "@type": "Product",
      "name": "Test Product",
      "offers": {
        "@type": "Offer",
        "price": "29.99",
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock"
      }
    }
    </script>
    <meta property="og:price:amount" content="29.99">
    <meta property="og:price:currency" content="USD">
</head>
<body>
    <h1 id="productTitle">Test Product</h1>
    <span class="a-price-whole">29</span>
    <span class="a-price-fraction">99</span>
    <div id="availability">
        <span class="a-size-medium a-color-success">In Stock</span>
    </div>
    <img id="landingImage" src="https://example.com/image.jpg" />
</body>
</html>
```

Similar files for:
- `ebay_product.html`
- `walmart_product.html`
- `generic_product.html`

### P2 - Medium Priority

#### Task 7: Add Dockerfile

**Location**: `ExtractorPatternAgent/Dockerfile`

```dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application
COPY . .

ENV DATABASE_PATH=/app/db.sqlite3
ENV PYTHONPATH=/app:$PYTHONPATH

CMD ["python", "scripts/generate_pattern.py", "--help"]
```

#### Task 8: System Prompt Refinement

Test and refine the system prompt based on actual results:

```python
def _get_system_prompt(self) -> str:
    return """You are an expert web scraping pattern generator specializing in e-commerce sites.

Your task:
1. Analyze HTML structure from product pages
2. Generate reliable extraction patterns using CSS selectors, XPath, JSON-LD, or meta tags
3. Prioritize stable selectors over brittle ones
4. Always provide fallback options
5. Return structured JSON with confidence scores

Key fields to extract:
- **price**: Current selling price (not crossed-out/MSRP)
- **title**: Product name/title
- **availability**: In stock status (boolean)
- **image**: Primary product image URL

Extraction method priority (most to least reliable):
1. JSON-LD structured data (confidence: 0.95+)
   - Look for <script type="application/ld+json">
   - Parse Product schema

2. Meta tags (confidence: 0.85+)
   - og:price, product:price:amount
   - og:title, product:title

3. Semantic CSS selectors (confidence: 0.80+)
   - IDs: #productPrice, #productTitle
   - Data attributes: [data-price], [data-product-id]
   - Semantic classes: .product-price, .price-current

4. XPath with text matching (confidence: 0.70+)
   - Last resort for complex layouts
   - Use contains() for flexibility

Quality guidelines:
- Avoid auto-generated class names (e.g., css-1234abcd)
- Prefer IDs and data attributes over classes
- Test each selector before returning
- Provide 2-3 fallback options per field
- Note any assumptions or edge cases

Output format:
{
  "store_domain": "example.com",
  "patterns": {
    "price": {
      "primary": {"type": "jsonld", "selector": "...", "confidence": 0.95},
      "fallbacks": [...]
    },
    "title": {...},
    "availability": {...},
    "image": {...}
  },
  "metadata": {
    "validated_count": 1,
    "confidence_score": 0.90
  }
}
"""
```

## Testing Checklist

### Unit Tests
- [ ] Each tool works independently
- [ ] Browser tools fetch real pages
- [ ] Parser tools extract JSON-LD and meta tags
- [ ] Validator tools correctly validate data
- [ ] Storage tools save/load from Django database

### Integration Tests
- [ ] Agent generates patterns end-to-end
- [ ] Patterns saved to correct database table
- [ ] CLI interface works
- [ ] Can be called from WebUI subprocess

### Real-World Tests
- [ ] Generate pattern for Amazon product
- [ ] Generate pattern for eBay product
- [ ] Generate pattern for generic e-commerce site
- [ ] Verify patterns work with PriceFetcher

## Common Issues & Solutions

### Issue 1: Playwright not installed
```
playwright._impl._api_types.Error: Executable doesn't exist
```
**Solution**:
```bash
playwright install chromium
```

### Issue 2: Django import fails
```
ModuleNotFoundError: No module named 'app'
```
**Solution**: Check DJANGO_PATH is correct in storage.py

### Issue 3: Agent output doesn't match schema
```
ValidationError: 'primary' is required
```
**Solution**: Refine system prompt to ensure correct output format

### Issue 4: Pattern confidence too low
```
Warning: Pattern confidence 0.45 below threshold
```
**Solution**: Improve selector analysis, add more fallbacks

## Next Agent Handoff

After completing P0 and P1:
1. Run all tests: `pytest tests/ -v`
2. Generate pattern for real e-commerce site
3. Verify pattern saved correctly in Django database
4. Test CLI: `uv run extractor-cli.py generate <url>`
5. Test subprocess call from WebUI mock
6. Document any issues or edge cases found
7. Update this file with current status

## References

- Architecture: `ARCHITECTURE.md`
- Agent implementation: `src/agent.py`
- Claude Agent SDK docs: (see .claude/skills/agent-sdk/)
- Django models: `../WebUI/app/models.py`
