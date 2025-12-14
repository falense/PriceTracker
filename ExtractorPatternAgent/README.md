# ExtractorPatternAgent

AI-powered web scraping pattern generator built with Claude Agent SDK. Automatically analyzes e-commerce websites and generates reliable extraction patterns for product pricing and metadata.

## Features

- **Intelligent Pattern Generation**: Uses Claude AI to analyze HTML and generate optimal selectors
- **Multiple Extraction Strategies**: Prioritizes JSON-LD, meta tags, semantic CSS, and XPath
- **Automatic Validation**: Tests patterns and validates extracted data quality
- **Pattern Storage**: SQLite database for persistent pattern management
- **Rich CLI Interface**: User-friendly command-line tool with colored output
- **Flexible Architecture**: Modular design with custom MCP tools

## Installation

### Prerequisites

- Python 3.12 or higher
- UV package manager (recommended)
- Playwright browsers

### Quick Start with UV

```bash
# The CLI script is self-contained with PEP 723 headers
cd ExtractorPatternAgent
uv run extractor-cli.py --help

# Install Playwright browsers (first time only)
playwright install chromium
```

### Manual Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

### CLI Commands

#### Generate Patterns

Generate extraction patterns for a product URL:

```bash
uv run extractor-cli.py generate https://www.example.com/product/123

# Save to file
uv run extractor-cli.py generate https://www.example.com/product/123 -o patterns.json

# Use custom config
uv run extractor-cli.py generate https://www.example.com/product/123 -c config/settings.yaml
```

#### Validate Patterns

Test patterns against a URL:

```bash
# Validate patterns from database
uv run extractor-cli.py validate https://www.example.com/product/456 -d example.com

# Validate patterns from file
uv run extractor-cli.py validate https://www.example.com/product/456 -p patterns.json
```

#### List Stored Patterns

View all patterns in the database:

```bash
uv run extractor-cli.py list
```

#### Export Patterns

Export patterns to JSON:

```bash
uv run extractor-cli.py export example.com -o exported_patterns.json
```

#### Custom Queries

Send custom queries to the agent:

```bash
uv run extractor-cli.py query "What tools are available?"
```

### Python API

#### Basic Usage

```python
import asyncio
from src.agent import ExtractorPatternAgent

async def main():
    url = "https://www.example.com/product/123"

    async with ExtractorPatternAgent() as agent:
        # Generate patterns
        patterns = await agent.generate_patterns(url)
        print(patterns)

        # Validate patterns
        validation = await agent.validate_patterns(url, patterns)
        print(validation)

asyncio.run(main())
```

#### Advanced Usage with Validation Loop

```python
async def generate_with_validation(url: str, max_retries: int = 3):
    async with ExtractorPatternAgent() as agent:
        for attempt in range(max_retries):
            # Generate patterns
            patterns = await agent.generate_patterns(url, save_to_db=False)

            # Validate
            validation = await agent.validate_patterns(url, patterns)

            if validation["success"] and validation["overall_confidence"] >= 0.7:
                # Save successful patterns
                return patterns
            elif attempt < max_retries - 1:
                # Refine based on feedback
                feedback = f"Confidence too low: {validation['overall_confidence']}"
                patterns = await agent.refine_patterns(feedback)

        raise Exception("Failed to generate valid patterns")
```

## Architecture

### Components

```
ExtractorPatternAgent/
├── src/
│   ├── agent.py              # Main agent implementation
│   ├── tools/                # Custom MCP tools
│   │   ├── browser.py        # Playwright browser tools
│   │   ├── parser.py         # HTML analysis tools
│   │   ├── validator.py      # Pattern validation tools
│   │   └── storage.py        # SQLite storage tools
│   ├── models/               # Data models
│   │   ├── pattern.py        # Pattern data structures
│   │   └── validation.py     # Validation result models
│   └── utils/                # Utility functions
│       ├── html_utils.py     # HTML processing
│       └── selector_utils.py # Selector generation
├── config/
│   └── settings.yaml         # Configuration
├── examples/
│   ├── basic_usage.py        # Basic example
│   └── advanced_usage.py     # Advanced example with validation
├── tests/
│   ├── test_agent.py         # Agent tests
│   └── test_tools.py         # Tool tests
└── extractor-cli.py          # CLI interface (UV compatible)
```

### Pattern Structure

Generated patterns follow this schema:

```json
{
  "store_domain": "example.com",
  "patterns": {
    "price": {
      "primary": {
        "type": "css|xpath|jsonld|meta",
        "selector": "selector string",
        "confidence": 0.95,
        "attribute": "optional"
      },
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
```

## Configuration

Edit `config/settings.yaml` to customize:

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

validation:
  min_confidence: 0.7
  max_retries: 3
```

## Extraction Strategy

The agent prioritizes extraction methods in this order:

1. **JSON-LD** (confidence: 0.95+)
   - Most reliable, structured schema.org data
   - Example: `script[type="application/ld+json"]`

2. **Meta Tags** (confidence: 0.85+)
   - Open Graph and product-specific tags
   - Example: `<meta property="og:price" content="29.99">`

3. **Semantic CSS** (confidence: 0.80+)
   - IDs, data attributes, semantic classes
   - Example: `.product-price`, `[data-price]`, `#price`

4. **XPath** (confidence: 0.70+)
   - Last resort with text matching
   - Example: `//span[contains(@class, 'price')]`

## Tools Available

The agent has access to these custom MCP tools:

### Browser Tools
- `fetch_page`: Fetch HTML from URL
- `render_js`: Render JavaScript-heavy pages
- `screenshot_page`: Take page screenshots

### Parser Tools
- `extract_structured_data`: Extract JSON-LD and meta tags
- `analyze_selectors`: Analyze HTML for selector candidates
- `extract_with_selector`: Test extraction with specific selector

### Validator Tools
- `test_pattern`: Test selector against HTML
- `validate_extraction`: Validate extracted data format
- `validate_pattern_result`: Validate complete pattern result

### Storage Tools
- `save_pattern`: Save patterns to database
- `load_pattern`: Load patterns from database
- `list_patterns`: List all stored patterns
- `delete_pattern`: Delete patterns

## Testing

Run the test suite:

```bash
# Install pytest
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Examples

See the `examples/` directory for:
- `basic_usage.py`: Simple pattern generation
- `advanced_usage.py`: Validation loop with automatic refinement

Run examples:

```bash
python examples/basic_usage.py
python examples/advanced_usage.py https://www.example.com/product/123
```

## Troubleshooting

### Common Issues

1. **Playwright not installed**
   ```bash
   playwright install chromium
   ```

2. **Import errors**
   ```bash
   # Ensure you're in the ExtractorPatternAgent directory
   cd ExtractorPatternAgent
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

3. **Database locked**
   ```bash
   # Remove the database file
   rm patterns.db
   ```

## Development

### Project Structure

- `src/agent.py`: Core agent implementation using Claude SDK
- `src/tools/`: Custom MCP tools for web scraping
- `src/models/`: Pydantic models for data validation
- `src/utils/`: Helper functions for HTML and selector processing

### Adding New Tools

1. Create tool in `src/tools/`
2. Add to `src/tools/__init__.py`
3. Update agent's allowed_tools list in `src/agent.py`

### Adding New Field Types

1. Update extraction strategy in agent system prompt
2. Add validation logic in `src/tools/validator.py`
3. Update pattern schema in `src/models/pattern.py`

## Dependencies

Core dependencies:
- `claude-agent-sdk`: Claude Agent SDK
- `playwright`: Browser automation
- `beautifulsoup4`: HTML parsing
- `lxml`: XPath support
- `click`: CLI framework
- `rich`: Terminal formatting
- `pyyaml`: Configuration management

## License

MIT License

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

For issues and questions:
- Check the [Architecture documentation](ARCHITECTURE.md)
- Review the examples in `examples/`
- Open an issue on GitHub
