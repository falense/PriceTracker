# ExtractorPatternAgent

Web scraping pattern generator that analyzes e-commerce websites and generates reliable extraction patterns for product pricing and metadata.

## Features

- **Heuristic Pattern Generation**: Analyzes HTML structure to find price, title, image, and availability data
- **Multiple Extraction Strategies**: Prioritizes JSON-LD, meta tags, semantic CSS, and XPath
- **Stealth Browser**: Uses Playwright with anti-detection measures
- **Pattern Storage**: SQLite database for persistent pattern management
- **Rich CLI Interface**: User-friendly command-line tool with colored output

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

### Generate Patterns

Generate extraction patterns for a product URL:

```bash
# Basic usage
python generate_pattern.py https://www.example.com/product/123

# With domain override
python generate_pattern.py https://www.example.com/product/123 --domain example.com
```

The script will:
1. Fetch the page using Playwright with stealth mode
2. Analyze HTML structure for price, title, image, and availability
3. Generate CSS/XPath selectors with fallbacks
4. Save patterns to a JSON file (e.g., `example_com_patterns.json`)

### Integration with Celery

The WebUI Celery tasks call this script via subprocess:

```python
# From WebUI/app/tasks.py
result = subprocess.run([
    'python',
    '/extractor/generate_pattern.py',
    url,
    '--domain', domain
], ...)
```

### CLI Tool (Alternative)

The `extractor-cli.py` provides additional commands:

```bash
# List stored patterns
uv run extractor-cli.py list

# Export patterns
uv run extractor-cli.py export example.com -o exported_patterns.json
```

## Architecture

### Components

```
ExtractorPatternAgent/
├── generate_pattern.py       # Main pattern generator (used in production)
├── extractor-cli.py          # CLI interface
├── src/
│   ├── utils/
│   │   ├── stealth.py        # Anti-detection utilities
│   │   ├── html_utils.py     # HTML processing
│   │   └── selector_utils.py # Selector generation
│   ├── models/               # Data models
│   │   ├── pattern.py        # Pattern data structures
│   │   └── validation.py     # Validation result models
│   └── tools/                # Tool implementations
│       ├── parser.py         # HTML analysis
│       └── validator.py      # Pattern validation
├── config/
│   └── settings.yaml         # Configuration
├── examples/
│   └── basic_usage.py        # Usage example
└── tests/                    # Test files
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

## Extraction Methods

The pattern generator tries these methods in order:

1. **data-price attribute**: `[data-price]` elements
2. **JSON-LD**: `<script type="application/ld+json">` structured data
3. **Meta tags**: Open Graph (`og:price:amount`) and product meta tags
4. **CSS selectors**: Common patterns like `.price`, `.product-price`, `#price`
5. **Class-based**: Elements with "price" in class name

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

- `generate_pattern.py`: Main pattern generator script
- `src/utils/stealth.py`: Browser anti-detection utilities
- `src/models/`: Data models for patterns and validation
- `src/tools/`: Parser and validator utilities

### Adding New Field Types

1. Add extraction logic in `generate_pattern.py` `analyze_html()` function
2. Add validation logic in `src/tools/validator.py`
3. Update pattern schema in `src/models/pattern.py`

## Dependencies

Core dependencies:
- `playwright`: Browser automation with stealth capabilities
- `beautifulsoup4`: HTML parsing
- `lxml`: XPath support
- `rich`: Terminal formatting

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
- Review the examples in `examples/`
- Check the main project [README](../README.md)
