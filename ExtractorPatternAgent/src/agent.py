"""Main ExtractorPatternAgent implementation using Claude Agent SDK."""

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from typing import Dict, Any, Optional, AsyncGenerator
import json
import logging
from pathlib import Path
import yaml

from .tools import (
    fetch_page_tool, render_js_tool, screenshot_page_tool,
    extract_structured_data_tool, analyze_selectors_tool, extract_with_selector_tool,
    test_pattern_tool, validate_extraction_tool, validate_pattern_result_tool,
    save_pattern_tool, load_pattern_tool, list_patterns_tool, delete_pattern_tool
)
from .models.pattern import Pattern, PatternResult
from .models.validation import ValidationResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractorPatternAgent:
    """
    AI agent that generates and validates extraction patterns for web scraping.

    Uses Claude Agent SDK to analyze e-commerce websites and generate reliable
    extraction patterns for product pricing and metadata.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_file: Optional[str] = None):
        """
        Initialize the ExtractorPatternAgent.

        Args:
            config: Configuration dictionary
            config_file: Path to YAML configuration file
        """
        self.config = self._load_config(config, config_file)
        self.client: Optional[ClaudeSDKClient] = None
        self.mcp_server = None

    def _load_config(self, config: Optional[Dict[str, Any]], config_file: Optional[str]) -> Dict[str, Any]:
        """
        Load configuration from dict or file.

        Args:
            config: Configuration dictionary
            config_file: Path to YAML configuration file

        Returns:
            Merged configuration dictionary
        """
        default_config = {
            "agent": {
                "model": "claude-sonnet-4-5-20250929",
                "max_turns": 20,
                "timeout": 300
            },
            "browser": {
                "headless": True,
                "timeout": 30000,
                "viewport": {
                    "width": 1920,
                    "height": 1080
                }
            },
            "validation": {
                "min_confidence": 0.7,
                "max_retries": 3
            }
        }

        # Load from file if provided
        if config_file:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        default_config.update(file_config)

        # Override with provided config
        if config:
            default_config.update(config)

        return default_config

    def _setup_mcp_server(self):
        """Setup MCP server with all custom tools."""
        tools = [
            fetch_page_tool,
            render_js_tool,
            screenshot_page_tool,
            extract_structured_data_tool,
            analyze_selectors_tool,
            extract_with_selector_tool,
            test_pattern_tool,
            validate_extraction_tool,
            validate_pattern_result_tool,
            save_pattern_tool,
            load_pattern_tool,
            list_patterns_tool,
            delete_pattern_tool,
        ]

        self.mcp_server = create_sdk_mcp_server(
            name="extractor",
            version="1.0.0",
            tools=tools
        )

        logger.info("MCP server initialized with all tools")

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the agent.

        Returns:
            System prompt string
        """
        return """You are an expert web scraping pattern generator specialized in e-commerce websites.

Your task is to analyze HTML structure from e-commerce websites and generate reliable extraction patterns for product data.

## Core Capabilities

1. **HTML Analysis**: Parse and understand complex HTML structures
2. **Pattern Generation**: Create robust CSS/XPath selectors for data extraction
3. **Validation**: Test patterns to ensure they work correctly
4. **Optimization**: Prioritize stable, maintainable selectors

## Key Fields to Extract

- **price**: Current selling price (not strikethrough/original price)
- **title**: Product name/title
- **availability**: In stock status
- **image**: Primary product image URL

## Extraction Strategy Priority

Always generate patterns in this order of preference:

1. **JSON-LD structured data** (highest reliability, confidence: 0.95+)
   - Look for script tags with type="application/ld+json"
   - Extract Product schema data

2. **Meta tags** (high reliability, confidence: 0.85+)
   - Open Graph tags (og:price, og:title, og:image)
   - Product-specific meta tags

3. **Semantic CSS selectors** (good reliability, confidence: 0.80+)
   - IDs and data attributes
   - Semantic class names (avoid auto-generated classes)
   - Microdata attributes (itemprop)

4. **XPath with text matching** (last resort, confidence: 0.70+)
   - Use only when other methods fail
   - Combine with context for stability

## Pattern Quality Guidelines

- **Prefer** selectors that are unlikely to change (IDs, semantic classes, data attributes)
- **Avoid** selectors based on position (nth-child) unless necessary
- **Avoid** randomly generated class names (e.g., `_abc123xyz`)
- **Always** provide fallback patterns for resilience
- **Test** each pattern to verify it extracts valid data

## Workflow

When given a URL to analyze:

1. Fetch the page HTML (use `fetch_page` or `render_js` tool)
2. Extract structured data (use `extract_structured_data` tool)
3. For each field:
   a. Check if data exists in JSON-LD or meta tags
   b. If not, analyze HTML for selector candidates (use `analyze_selectors` tool)
   c. Generate primary selector and fallbacks
   d. Test each selector (use `test_pattern` tool)
   e. Validate extracted data format (use `validate_extraction` tool)
4. Compile patterns with confidence scores
5. Save patterns if successful (use `save_pattern` tool)

## Output Format

Return patterns as structured JSON matching this schema:
```json
{
  "store_domain": "example.com",
  "patterns": {
    "price": {
      "primary": {
        "type": "jsonld|css|xpath|meta",
        "selector": "selector string",
        "confidence": 0.0-1.0,
        "attribute": "optional attribute name"
      },
      "fallbacks": [...]
    },
    "title": {...},
    "availability": {...},
    "image": {...}
  },
  "metadata": {
    "validated_count": 1,
    "confidence_score": 0.85
  }
}
```

Always be thorough, test your patterns, and prioritize reliability over convenience."""

    async def __aenter__(self):
        """Initialize agent session (async context manager)."""
        logger.info("Initializing ExtractorPatternAgent")

        # Setup MCP server with tools
        self._setup_mcp_server()

        # Create agent options
        options = ClaudeAgentOptions(
            system_prompt=self._get_system_prompt(),
            mcp_servers={"extractor": self.mcp_server},
            allowed_tools=[
                "mcp__extractor__fetch_page",
                "mcp__extractor__render_js",
                "mcp__extractor__screenshot_page",
                "mcp__extractor__extract_structured_data",
                "mcp__extractor__analyze_selectors",
                "mcp__extractor__extract_with_selector",
                "mcp__extractor__test_pattern",
                "mcp__extractor__validate_extraction",
                "mcp__extractor__validate_pattern_result",
                "mcp__extractor__save_pattern",
                "mcp__extractor__load_pattern",
                "mcp__extractor__list_patterns",
                "mcp__extractor__delete_pattern",
            ],
            permission_mode="acceptEdits",
            max_turns=self.config["agent"]["max_turns"],
        )

        # Initialize client
        self.client = ClaudeSDKClient(options)
        await self.client.connect()

        logger.info("ExtractorPatternAgent initialized successfully")
        return self

    async def __aexit__(self, *args):
        """Cleanup agent session."""
        if self.client:
            await self.client.disconnect()
        logger.info("ExtractorPatternAgent session closed")

    async def generate_patterns(self, url: str, save_to_db: bool = True) -> Dict[str, Any]:
        """
        Generate extraction patterns for a product URL.

        Args:
            url: Product page URL to analyze
            save_to_db: Whether to save patterns to database (default: True)

        Returns:
            Dictionary with extraction patterns and metadata
        """
        logger.info(f"Generating patterns for URL: {url}")

        prompt = f"""Generate extraction patterns for this product page: {url}

Follow these steps carefully:

1. Fetch the page HTML using the fetch_page tool
2. Extract structured data (JSON-LD, meta tags) using extract_structured_data tool
3. For each required field (price, title, availability, image):
   a. Check if data exists in structured data
   b. If not, analyze HTML for selector candidates using analyze_selectors tool
   c. Generate primary selector and test it using test_pattern tool
   d. Validate the extracted data using validate_extraction tool
   e. Generate 1-2 fallback selectors if possible
4. Compile all patterns with confidence scores
5. {'Save the patterns using save_pattern tool' if save_to_db else 'Do not save to database'}

Return the complete pattern structure as JSON.

Prioritize patterns in this order:
- JSON-LD structured data (confidence: 0.95+)
- Meta tags (confidence: 0.85+)
- Semantic CSS selectors (confidence: 0.80+)
- XPath fallback (confidence: 0.70+)

Make sure to test each pattern before including it in the final result."""

        # Send query to agent
        await self.client.query(prompt)

        # Collect response
        result = await self._collect_response()

        logger.info("Pattern generation completed")
        return result

    async def validate_patterns(self, url: str, patterns: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate extraction patterns against a URL.

        Args:
            url: Product page URL to test against
            patterns: Patterns to validate (if None, loads from database)

        Returns:
            Validation results with success/failure details
        """
        logger.info(f"Validating patterns for URL: {url}")

        if patterns is None:
            # Extract domain from URL
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            prompt = f"""Load and validate patterns for {url}

Steps:
1. Load the patterns for domain '{domain}' using load_pattern tool
2. Fetch the page HTML using fetch_page tool
3. Test each pattern selector using test_pattern tool
4. Validate each extracted value using validate_extraction tool
5. Return validation results with success/failure for each field

Provide detailed feedback on any failures."""

        else:
            prompt = f"""Validate these extraction patterns against {url}:

Patterns:
{json.dumps(patterns, indent=2)}

Steps:
1. Fetch the page HTML using fetch_page tool
2. For each pattern in the patterns:
   a. Test the primary selector using test_pattern tool
   b. Validate the extracted value using validate_extraction tool
   c. If primary fails, test fallback selectors
3. Return validation results including:
   - Which fields succeeded/failed
   - Extracted values for successful fields
   - Error messages for failed fields
   - Overall confidence score"""

        # Send query to agent
        await self.client.query(prompt)

        # Collect response
        result = await self._collect_response()

        logger.info("Pattern validation completed")
        return result

    async def refine_patterns(self, feedback: str) -> Dict[str, Any]:
        """
        Refine patterns based on validation feedback.

        Uses same conversation context to maintain awareness of previous attempts.

        Args:
            feedback: Description of what failed and needs refinement

        Returns:
            Refined patterns
        """
        logger.info("Refining patterns based on feedback")

        prompt = f"""The previous patterns failed validation with this feedback:

{feedback}

Please refine the patterns to address these issues:

1. Analyze why the patterns failed
2. Generate improved selectors that are more robust
3. Test the new patterns using test_pattern tool
4. Validate extracted data using validate_extraction tool
5. Return the refined patterns

Focus on more reliable selectors and add better fallback options."""

        # Send query to agent (continues existing conversation)
        await self.client.query(prompt)

        # Collect response
        result = await self._collect_response()

        logger.info("Pattern refinement completed")
        return result

    async def _collect_response(self) -> Dict[str, Any]:
        """
        Collect complete response from the agent.

        Returns:
            Parsed response data
        """
        result = {}
        full_response = []

        async for message in self.client.receive_response():
            # Collect all text content
            if hasattr(message, 'content'):
                if isinstance(message.content, list):
                    for content_block in message.content:
                        if hasattr(content_block, 'text'):
                            full_response.append(content_block.text)
                elif hasattr(message.content, 'text'):
                    full_response.append(message.content.text)

        # Try to extract JSON from response
        response_text = '\n'.join(full_response)

        # Look for JSON blocks in markdown code blocks
        import re
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                result = {"response": response_text}
        else:
            # Try to parse entire response as JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = {"response": response_text}

        return result

    async def list_stored_patterns(self) -> Dict[str, Any]:
        """
        List all patterns stored in the database.

        Returns:
            Dictionary with list of stored patterns
        """
        logger.info("Listing stored patterns")

        prompt = """List all stored extraction patterns.

Use the list_patterns tool to retrieve all patterns from the database.

Return a summary including:
- Total number of patterns
- Domain names
- Confidence scores
- Last updated timestamps"""

        await self.client.query(prompt)
        result = await self._collect_response()

        return result

    async def query(self, prompt: str) -> Dict[str, Any]:
        """
        Send a custom query to the agent.

        Args:
            prompt: Custom prompt/question

        Returns:
            Agent's response
        """
        logger.info("Sending custom query to agent")

        await self.client.query(prompt)
        result = await self._collect_response()

        return result
