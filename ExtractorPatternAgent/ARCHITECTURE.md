# Extractor Pattern Agent

## Purpose

AI agent built with Claude Agent SDK that analyzes e-commerce web pages and generates reusable extraction patterns for product pricing and metadata. Adapts to layout changes using LLM-powered analysis.

## Architecture

### Agent Design

```
Input: Product URL
    ↓
┌─────────────────────────────────┐
│  ExtractorPatternAgent          │
│  (Claude SDK Agent)             │
│                                 │
│  Tools:                         │
│  - Browser (fetch, render)      │
│  - Parser (analyze HTML)        │
│  - Validator (test patterns)    │
│  - Storage (save patterns)      │
└─────────────────────────────────┘
    ↓
Output: Validated extraction patterns (JSON)
```

### Component Structure

```
ExtractorPatternAgent/
├── ARCHITECTURE.md
├── src/
│   ├── agent.py              # Main agent implementation
│   ├── tools/
│   │   ├── browser.py        # Playwright browser tools
│   │   ├── parser.py         # HTML analysis tools
│   │   ├── validator.py      # Pattern validation tools
│   │   └── storage.py        # Pattern storage tools
│   ├── models/
│   │   ├── pattern.py        # Pattern data models
│   │   └── validation.py     # Validation result models
│   └── utils/
│       ├── html_utils.py     # HTML processing utilities
│       └── selector_utils.py # CSS/XPath helpers
├── config/
│   └── settings.yaml         # Agent configuration
├── tests/
│   ├── test_agent.py
│   ├── test_tools.py
│   └── fixtures/
│       └── sample_pages/     # Test HTML files
└── examples/
    ├── basic_usage.py
    └── advanced_usage.py
```

## Agent Implementation

### Core Agent Class

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from typing import Dict, Any
import json

class ExtractorPatternAgent:
    """
    Agent that generates and validates extraction patterns for web scraping.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._default_config()
        self.tools = self._setup_tools()
        self.client = None

    def _setup_tools(self):
        """Setup MCP server with custom tools."""
        from .tools import browser, parser, validator, storage

        tools = [
            browser.fetch_page_tool,
            browser.render_js_tool,
            parser.extract_structured_data_tool,
            parser.analyze_selectors_tool,
            validator.test_pattern_tool,
            validator.validate_extraction_tool,
            storage.save_pattern_tool,
            storage.load_pattern_tool
        ]

        return create_sdk_mcp_server(
            name="extractor",
            version="1.0.0",
            tools=tools
        )

    async def __aenter__(self):
        """Initialize agent session."""
        system_prompt = """You are an expert web scraping pattern generator.

Your task is to:
1. Analyze HTML structure from e-commerce websites
2. Generate reliable CSS/XPath selectors for product data
3. Prioritize stable selectors (IDs, semantic classes over generated classes)
4. Validate patterns work correctly
5. Return structured JSON with high-confidence patterns

Key fields to extract:
- price: Current selling price (not strikethrough/original)
- title: Product name
- availability: In stock status
- image: Primary product image URL

Always generate multiple fallback strategies:
1. JSON-LD structured data (highest reliability)
2. Meta tags (og:price, product:price)
3. Semantic CSS selectors
4. XPath with text matching (last resort)
"""

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={"extractor": self.tools},
            allowed_tools=[
                "mcp__extractor__fetch_page",
                "mcp__extractor__render_js",
                "mcp__extractor__extract_structured_data",
                "mcp__extractor__analyze_selectors",
                "mcp__extractor__test_pattern",
                "mcp__extractor__validate_extraction",
                "mcp__extractor__save_pattern",
                "mcp__extractor__load_pattern",
                "Read", "Write"
            ],
            permission_mode="acceptEdits",
            output_format={
                "type": "json_schema",
                "schema": self._output_schema()
            },
            max_turns=20
        )

        self.client = ClaudeSDKClient(options)
        await self.client.connect()
        return self

    async def __aexit__(self, *args):
        """Cleanup agent session."""
        if self.client:
            await self.client.disconnect()

    async def generate_patterns(self, url: str) -> Dict[str, Any]:
        """
        Generate extraction patterns for a product URL.

        Args:
            url: Product page URL

        Returns:
            Dictionary with extraction patterns and confidence scores
        """
        prompt = f"""Generate extraction patterns for this product page: {url}

Steps:
1. Fetch the page HTML (use fetch_page tool)
2. Check for JSON-LD structured data (extract_structured_data tool)
3. Analyze HTML structure for reliable selectors (analyze_selectors tool)
4. Generate patterns for: price, title, availability, image
5. Test each pattern (test_pattern tool)
6. Validate extraction quality (validate_extraction tool)
7. Return patterns with confidence scores

Prioritize patterns in this order:
- JSON-LD (confidence: 0.95+)
- Meta tags (confidence: 0.85+)
- Semantic CSS (confidence: 0.80+)
- XPath fallback (confidence: 0.70+)
"""

        await self.client.query(prompt)

        result = None
        async for message in self.client.receive_response():
            if isinstance(message, ResultMessage):
                result = json.loads(message.result)
                break

        return result

    async def validate_patterns(self, url: str, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate patterns against a URL.

        Args:
            url: Product page URL
            patterns: Previously generated patterns

        Returns:
            Validation results with success/failure details
        """
        prompt = f"""Validate these extraction patterns against {url}:

Patterns: {json.dumps(patterns, indent=2)}

For each pattern:
1. Fetch the page
2. Apply the selector
3. Validate extracted data format
4. Return success/failure with details
"""

        await self.client.query(prompt)

        result = None
        async for message in self.client.receive_response():
            if isinstance(message, ResultMessage):
                result = json.loads(message.result)
                break

        return result

    async def refine_patterns(self, feedback: str) -> Dict[str, Any]:
        """
        Refine patterns based on validation feedback.
        Uses same conversation context to maintain awareness of previous attempts.

        Args:
            feedback: Description of what failed

        Returns:
            Refined patterns
        """
        prompt = f"""The previous patterns failed validation:

{feedback}

Please refine the patterns to address these issues. Focus on more robust selectors.
"""

        await self.client.query(prompt)

        result = None
        async for message in self.client.receive_response():
            if isinstance(message, ResultMessage):
                result = json.loads(message.result)
                break

        return result

    def _output_schema(self) -> Dict[str, Any]:
        """JSON Schema for structured output."""
        return {
            "type": "object",
            "properties": {
                "store_domain": {"type": "string"},
                "patterns": {
                    "type": "object",
                    "properties": {
                        "price": self._pattern_schema(),
                        "title": self._pattern_schema(),
                        "availability": self._pattern_schema(),
                        "image": self._pattern_schema()
                    },
                    "required": ["price", "title"]
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "validated_count": {"type": "integer"},
                        "confidence_score": {"type": "number"}
                    }
                }
            },
            "required": ["store_domain", "patterns"]
        }

    def _pattern_schema(self) -> Dict[str, Any]:
        """Schema for individual pattern."""
        return {
            "type": "object",
            "properties": {
                "primary": {
                    "type": "object",
                    "properties": {
                        "type": {"enum": ["css", "xpath", "jsonld", "meta"]},
                        "selector": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "attribute": {"type": "string"}
                    },
                    "required": ["type", "selector", "confidence"]
                },
                "fallbacks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"enum": ["css", "xpath", "jsonld", "meta"]},
                            "selector": {"type": "string"},
                            "confidence": {"type": "number"}
                        }
                    }
                }
            },
            "required": ["primary"]
        }

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration."""
        return {
            "browser": {
                "headless": True,
                "timeout": 30000,
                "viewport": {"width": 1920, "height": 1080}
            },
            "validation": {
                "min_confidence": 0.7,
                "max_retries": 3
            }
        }
```

## Custom Tools

### Browser Tools (browser.py)

```python
from claude_agent_sdk import tool
from playwright.async_api import async_playwright
from typing import Any

@tool(
    "fetch_page",
    "Fetch HTML from a URL using headless browser",
    {"url": str, "wait_for_js": bool}
)
async def fetch_page_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Fetch page HTML with Playwright."""
    url = args["url"]
    wait_for_js = args.get("wait_for_js", True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until="networkidle" if wait_for_js else "domcontentloaded")
            html = await page.content()

            return {
                "content": [{
                    "type": "text",
                    "text": f"Successfully fetched page. HTML length: {len(html)}\n\n{html[:5000]}"
                }]
            }
        finally:
            await browser.close()

@tool(
    "render_js",
    "Render JavaScript-heavy page and extract final HTML",
    {"url": str, "wait_selector": str}
)
async def render_js_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Render JS and wait for specific selector."""
    url = args["url"]
    wait_selector = args.get("wait_selector")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until="networkidle")

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=10000)

            html = await page.content()

            return {
                "content": [{
                    "type": "text",
                    "text": html
                }]
            }
        finally:
            await browser.close()
```

### Parser Tools (parser.py)

```python
from claude_agent_sdk import tool
from bs4 import BeautifulSoup
import json

@tool(
    "extract_structured_data",
    "Extract JSON-LD or meta tag structured data",
    {"html": str}
)
async def extract_structured_data_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Extract structured data from HTML."""
    html = args["html"]
    soup = BeautifulSoup(html, 'html.parser')

    # Try JSON-LD
    jsonld_scripts = soup.find_all('script', type='application/ld+json')
    jsonld_data = []
    for script in jsonld_scripts:
        try:
            data = json.loads(script.string)
            jsonld_data.append(data)
        except:
            pass

    # Try meta tags
    meta_tags = {}
    for meta in soup.find_all('meta'):
        if meta.get('property') or meta.get('name'):
            key = meta.get('property') or meta.get('name')
            value = meta.get('content')
            if value:
                meta_tags[key] = value

    result = {
        "jsonld": jsonld_data,
        "meta_tags": meta_tags
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, indent=2)
        }]
    }

@tool(
    "analyze_selectors",
    "Analyze HTML structure and suggest reliable selectors",
    {"html": str, "field": str}
)
async def analyze_selectors_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze HTML for good selector candidates."""
    html = args["html"]
    field = args["field"]  # "price", "title", etc.

    soup = BeautifulSoup(html, 'html.parser')

    # Heuristic selector suggestions based on field type
    candidates = []

    if field == "price":
        # Look for price-related classes
        price_elements = soup.find_all(class_=lambda c: c and 'price' in c.lower())
        candidates = [{"selector": f".{el.get('class')[0]}", "type": "css"} for el in price_elements[:5]]

    elif field == "title":
        # Look for h1, product-title, etc.
        title_candidates = soup.find_all(['h1', 'h2'])
        candidates = [{"selector": el.name, "type": "css"} for el in title_candidates[:3]]

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(candidates, indent=2)
        }]
    }
```

### Validator Tools (validator.py)

```python
from claude_agent_sdk import tool
from bs4 import BeautifulSoup
import re

@tool(
    "test_pattern",
    "Test a selector pattern against HTML",
    {"html": str, "selector": str, "selector_type": str}
)
async def test_pattern_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Test if selector extracts valid data."""
    html = args["html"]
    selector = args["selector"]
    selector_type = args["selector_type"]  # "css" or "xpath"

    soup = BeautifulSoup(html, 'html.parser')

    try:
        if selector_type == "css":
            element = soup.select_one(selector)
            value = element.get_text(strip=True) if element else None
        else:
            # XPath would need lxml
            value = None

        success = value is not None and len(value) > 0

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": success,
                    "extracted_value": value,
                    "selector": selector
                })
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e)
                })
            }]
        }

@tool(
    "validate_extraction",
    "Validate extracted data format and quality",
    {"field": str, "value": str}
)
async def validate_extraction_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Validate extracted value is correct format."""
    field = args["field"]
    value = args["value"]

    if field == "price":
        # Check if looks like a price
        has_number = bool(re.search(r'\d+\.?\d*', value))
        has_currency = bool(re.search(r'[$€£¥]', value))
        valid = has_number

    elif field == "title":
        # Title should be 5-200 chars
        valid = 5 <= len(value) <= 200

    elif field == "availability":
        # Should contain stock-related keywords
        valid = any(kw in value.lower() for kw in ['stock', 'available', 'unavailable'])

    else:
        valid = len(value) > 0

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "valid": valid,
                "field": field,
                "value": value
            })
        }]
    }
```

### Storage Tools (storage.py)

```python
from claude_agent_sdk import tool
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "patterns.db"

@tool(
    "save_pattern",
    "Save extraction pattern to database",
    {"domain": str, "patterns": dict}
)
async def save_pattern_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Save patterns to SQLite."""
    domain = args["domain"]
    patterns = args["patterns"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO patterns (domain, pattern_json, created_at)
        VALUES (?, ?, datetime('now'))
    """, (domain, json.dumps(patterns)))

    conn.commit()
    conn.close()

    return {
        "content": [{
            "type": "text",
            "text": f"Saved patterns for {domain}"
        }]
    }

@tool(
    "load_pattern",
    "Load extraction pattern from database",
    {"domain": str}
)
async def load_pattern_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Load patterns from SQLite."""
    domain = args["domain"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pattern_json FROM patterns WHERE domain = ?
    """, (domain,))

    row = cursor.fetchone()
    conn.close()

    if row:
        patterns = json.loads(row[0])
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(patterns, indent=2)
            }]
        }
    else:
        return {
            "content": [{
                "type": "text",
                "text": f"No patterns found for {domain}"
            }]
        }
```

## Usage Examples

### Basic Pattern Generation

```python
import asyncio

async def main():
    url = "https://amazon.com/product/B0X123"

    async with ExtractorPatternAgent() as agent:
        # Generate patterns
        patterns = await agent.generate_patterns(url)
        print(f"Generated patterns: {patterns}")

        # Save to file
        with open("patterns/amazon.json", "w") as f:
            json.dump(patterns, f, indent=2)

asyncio.run(main())
```

### Pattern Validation Loop

```python
async def generate_with_validation(url: str, max_retries: int = 3):
    async with ExtractorPatternAgent() as agent:
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1}/{max_retries}")

            # Generate patterns
            patterns = await agent.generate_patterns(url)

            # Validate
            validation = await agent.validate_patterns(url, patterns)

            if validation["success"]:
                print("✓ Patterns validated successfully")
                return patterns
            else:
                print(f"✗ Validation failed: {validation['errors']}")

                if attempt < max_retries - 1:
                    # Refine based on feedback
                    patterns = await agent.refine_patterns(
                        feedback=validation['errors']
                    )

        raise Exception("Failed to generate valid patterns")
```

## Configuration

### settings.yaml

```yaml
agent:
  model: "claude-sonnet-4-5-20250929"
  max_turns: 20
  timeout: 300

browser:
  headless: true
  timeout: 30000
  viewport:
    width: 1920
    height: 1080
  user_agent: "Mozilla/5.0..."

validation:
  min_confidence: 0.7
  max_retries: 3
  test_urls_per_domain: 5

storage:
  database: "patterns.db"
  backup_enabled: true
  backup_interval: 86400
```

## Testing Strategy

```python
# tests/test_agent.py
import pytest
from src.agent import ExtractorPatternAgent

@pytest.mark.asyncio
async def test_generate_patterns():
    async with ExtractorPatternAgent() as agent:
        patterns = await agent.generate_patterns(
            "https://example.com/product/123"
        )

        assert "store_domain" in patterns
        assert "patterns" in patterns
        assert "price" in patterns["patterns"]
        assert patterns["patterns"]["price"]["primary"]["confidence"] > 0.7

@pytest.mark.asyncio
async def test_validate_patterns():
    async with ExtractorPatternAgent() as agent:
        patterns = {...}  # Mock patterns
        validation = await agent.validate_patterns(
            "https://example.com/product/456",
            patterns
        )

        assert "success" in validation
```

## Next Steps

1. Implement `ExtractorPatternAgent` class
2. Build custom tools (browser, parser, validator, storage)
3. Create data models for patterns
4. Add comprehensive tests
5. Build example scripts
6. Add monitoring and logging
