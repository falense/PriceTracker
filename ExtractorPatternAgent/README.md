# ExtractorPatternAgent

Web scraping pattern generator that analyzes e-commerce websites and generates reliable extraction patterns for product pricing and metadata.

## Overview

The ExtractorPatternAgent is a **production component** of the PriceTracker system, fully integrated with Django, PostgreSQL, and Celery. It automatically analyzes product pages and generates CSS/XPath selectors for extracting 6 key fields.

**Key Integration Points:**
- 🗄️ **PostgreSQL Storage** - Patterns stored in Django ORM (`Pattern` & `PatternHistory` models)
- ⚙️ **Celery Tasks** - Async pattern generation via `generate_pattern` task
- 📊 **Success Tracking** - Automatic reliability metrics per pattern
- 🔄 **Version Control** - Full audit trail of pattern changes with rollback
- 🧪 **Testing Service** - Built-in pattern validation and testing
- 🎛️ **Admin UI** - Django Admin interface for pattern management

## Features

- **Heuristic Pattern Generation**: Analyzes HTML structure to find 6 product fields
- **Multiple Extraction Strategies**: Prioritizes JSON-LD, meta tags, semantic CSS, and XPath
- **Stealth Browser**: Uses Playwright with comprehensive anti-detection measures
- **Pattern Versioning**: Automatic version control with full change history
- **Success Metrics**: Tracks extraction success rate per pattern
- **PostgreSQL Storage**: Production patterns stored via Django ORM
- **Celery Integration**: Async task queue for pattern generation
- **Testing & Validation**: Built-in services for pattern testing and validation

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

### Python API (Recommended for Integration)

The `PatternGenerator` class provides a clean async API for integration with Django, Celery, and other Python applications:

```python
from ExtractorPatternAgent import PatternGenerator

# Initialize the generator
generator = PatternGenerator()

# Generate patterns (async)
pattern_data = await generator.generate(url="https://example.com/product", domain="example.com")

# Pattern data contains:
# {
#   "store_domain": "example.com",
#   "url": "https://example.com/product",
#   "patterns": {
#     "price": {"primary": {...}, "fallbacks": [...]},
#     "title": {...},
#     "image": {...},
#     "availability": {...}
#   },
#   "metadata": {
#     "fields_found": 4,
#     "overall_confidence": 0.85,
#     ...
#   }
# }
```

**Production Celery Integration:**

The ExtractorPatternAgent is integrated via the `generate_pattern` Celery task in `WebUI/app/tasks.py`:

```python
from app.tasks import generate_pattern

# Queue pattern generation (async, non-blocking)
task = generate_pattern.delay(
    url="https://example.com/product/123",
    domain="example.com",
    listing_id="uuid-optional"  # If provided, auto-triggers price fetch
)

# Check task status
result = AsyncResult(task.id)
if result.ready():
    pattern_data = result.get()
```

**What the task does:**
1. Creates `PatternGenerator` instance
2. Fetches and analyzes the URL
3. Saves pattern to `Pattern` model (PostgreSQL)
4. Creates initial `PatternHistory` entry
5. Optionally queues price fetch task
6. Returns pattern data with status

### CLI Scripts (Legacy)

For manual testing and debugging, use the standalone scripts:

#### Generate Patterns (generate_pattern.py)

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

**Note:** For production use, prefer the Python API over subprocess calls.

#### CLI Tool (Alternative)

The `extractor-cli.py` provides additional commands:

The `extractor-cli.py` provides additional commands:

```bash
# List stored patterns
uv run extractor-cli.py list

# Export patterns
uv run extractor-cli.py export example.com -o exported_patterns.json
```

## Integration with PriceTracker

The ExtractorPatternAgent is fully integrated with the PriceTracker Django application:

### Database Integration

Patterns are stored in **PostgreSQL** (not SQLite) via Django ORM:

- **`Pattern` model** - Stores current patterns per store domain
- **`PatternHistory` model** - Tracks all version changes with audit trail

### Celery Task Integration

Patterns are generated via the Celery task `generate_pattern`:

```python
from app.tasks import generate_pattern

# Queue pattern generation task
task = generate_pattern.delay(
    url="https://example.com/product/123",
    domain="example.com",
    listing_id="uuid-here"  # Optional: auto-triggers price fetch after
)
```

**What happens:**
1. PatternGenerator fetches and analyzes the page
2. Pattern is saved to `Pattern` model in PostgreSQL
3. Initial `PatternHistory` entry created (version 1)
4. If `listing_id` provided, price fetch task auto-queued
5. Task returns pattern data and status

### Pattern Versioning

**Every pattern change is versioned automatically:**

```python
from app.pattern_services import PatternManagementService

# Update pattern (auto-creates history entry)
pattern = PatternManagementService.update_pattern(
    domain="example.com",
    pattern_json=new_pattern_data,
    user=request.user,
    change_reason="Fixed broken price selector"
)

# Rollback to previous version
pattern = PatternManagementService.rollback_pattern(
    domain="example.com",
    version_number=5,
    user=request.user
)

# View version history
history = PatternHistoryService.get_pattern_history("example.com", limit=20)
```

**PatternHistory tracks:**
- Version number (sequential)
- Pattern JSON snapshot
- Changed by (User FK)
- Change reason and type (manual_edit, auto_generated, rollback, etc.)
- Success rate at time of change
- Timestamp

### Success Rate Tracking

Patterns track their reliability automatically:

```python
pattern = Pattern.objects.get(domain="example.com")

# Record extraction attempt
pattern.record_attempt(success=True)  # Auto-updates success_rate

# Check health
if pattern.is_healthy:  # success_rate >= 60%
    print("Pattern is working well!")
```

**Metrics tracked:**
- `success_rate` - Percentage of successful extractions
- `total_attempts` - Number of extraction attempts
- `successful_attempts` - Number of successful extractions
- `last_validated` - Last test/validation timestamp

### Pattern Testing & Validation

Built-in services for testing patterns:

```python
from app.pattern_services import PatternTestService

# Test pattern against URL
result = PatternTestService.test_pattern_against_url(
    url="https://example.com/product",
    pattern_json=pattern.pattern_json,
    use_cache=True
)

# Returns:
# {
#   'success': True/False,
#   'extraction': {'price': {'value': '199.99', ...}, ...},
#   'selector_results': [...],  # Details on each selector
#   'errors': [],
#   'warnings': []
# }

# Validate pattern syntax
validation = PatternTestService.validate_pattern_syntax(pattern_json)
if not validation['valid']:
    print(validation['errors'])
```

### Admin Interface

Patterns are managed via Django Admin:

- `/admin/app/pattern/` - List all patterns with success rates
- Pattern detail view - Test, edit, view history
- Visual field testing - See which selectors match
- Version comparison - Diff between versions
- Rollback UI - One-click version rollback

### Data Flow

**Pattern Generation Flow:**
```
User adds product URL
       ↓
ProductListing created (no pattern exists for domain)
       ↓
generate_pattern.delay(url, domain, listing_id)
       ↓
PatternGenerator.generate(url, domain)
  ├─ fetch_page(url) → HTML
  ├─ analyze_html(html) → pattern_data
  └─ Return pattern_data
       ↓
Pattern.objects.update_or_create(domain, pattern_json)
       ↓
PatternHistory.objects.create(version=1, ...)
       ↓
[Optional] fetch_listing_price.delay(listing_id)
```

**Pattern Usage Flow:**
```
Celery scheduler triggers fetch_listing_price
       ↓
Get ProductListing and related Pattern
       ↓
PriceFetcher.fetch_price(url, pattern_json)
  ├─ Fetch HTML with Playwright
  ├─ Extract fields using pattern selectors
  └─ Return extracted data
       ↓
Pattern.record_attempt(success=True/False)
  ├─ Update success_rate
  └─ Increment total_attempts
       ↓
PriceHistory.objects.create(price, ...)
```

**Pattern Update Flow:**
```
Admin edits pattern via Django Admin
       ↓
PatternManagementService.update_pattern(...)
  ├─ Create PatternHistory entry (old version)
  ├─ Update Pattern.pattern_json (new version)
  └─ Increment version_number
       ↓
[Optional] Test pattern against URL
       ↓
Pattern.success_rate reset to 0.0
```

## API Reference

### PatternGenerator Class

The main class for pattern generation, designed for integration with Python applications.

**Constructor:**
```python
PatternGenerator(logger: Optional[structlog.BoundLogger] = None)
```

**Methods:**

#### `async generate(url: str, domain: str) -> Dict[str, Any]`

Generate extraction patterns for a product page.

**Parameters:**
- `url` (str): Product URL to analyze
- `domain` (str): Store domain (e.g., "amazon.com", "ebay.com")

**Returns:**
- `Dict[str, Any]`: Pattern data containing:
  - `store_domain`: Normalized domain
  - `url`: Original URL
  - `patterns`: Extraction patterns for each field (price, title, image, availability, article_number, model_number)
  - `metadata`: Generation metadata (fields_found, confidence, etc.)

**Example:**
```python
generator = PatternGenerator()
patterns = await generator.generate(
    url="https://www.amazon.com/dp/B08N5WRWNW",
    domain="amazon.com"
)
print(f"Found {patterns['metadata']['fields_found']} fields")
print(f"Confidence: {patterns['metadata']['overall_confidence']}")
```

**Integration Example:**
```python
from app.tasks import generate_pattern

# Production usage via Celery (recommended)
task = generate_pattern.delay(url, domain, listing_id)

# Direct usage (for testing/scripts)
from ExtractorPatternAgent import PatternGenerator
import asyncio

generator = PatternGenerator()
patterns = asyncio.run(generator.generate(url, domain))
```

#### `async fetch_page(url: str) -> str`

Fetch a page using Playwright with stealth capabilities.

**Parameters:**
- `url` (str): URL to fetch

**Returns:**
- `str`: HTML content

**Example:**
```python
generator = PatternGenerator()
html = await generator.fetch_page("https://example.com/product")
```

#### `analyze_html(html: str, url: str) -> Dict[str, Any]`

Analyze HTML and generate extraction patterns without fetching.

**Parameters:**
- `html` (str): HTML content to analyze
- `url` (str): Original URL (for domain extraction)

**Returns:**
- `Dict[str, Any]`: Pattern data (same structure as `generate()`)

**Example:**
```python
generator = PatternGenerator()
with open("product_page.html") as f:
    html = f.read()
patterns = generator.analyze_html(html, "https://example.com/product")
```

## Architecture

### Components

```
ExtractorPatternAgent/
├── generate_pattern.py       # Main pattern generator (used in production)
├── extractor-cli.py          # CLI interface (legacy)
├── src/
│   ├── pattern_generator.py  # Heuristic pattern generator (production)
│   ├── agent.py              # Claude SDK agent (advanced use cases)
│   ├── utils/
│   │   ├── stealth.py        # Anti-detection utilities
│   │   ├── html_utils.py     # HTML processing
│   │   └── selector_utils.py # Selector generation
│   ├── models/               # Data models
│   │   ├── pattern.py        # Pattern data structures
│   │   └── validation.py     # Validation result models
│   └── tools/                # Tool implementations
│       ├── parser.py         # HTML analysis
│       ├── validator.py      # Pattern validation
│       ├── storage.py        # SQLite storage (legacy)
│       └── browser.py        # Playwright utilities
├── config/
│   └── settings.yaml         # Configuration
├── examples/
│   └── basic_usage.py        # Usage example
└── tests/                    # Test files

WebUI/app/                     # PriceTracker integration
├── models.py                  # Pattern & PatternHistory models (PostgreSQL)
├── pattern_services.py        # Pattern management services
├── pattern_validators.py      # Pattern validation logic
└── tasks.py                   # Celery tasks (generate_pattern)
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

The PatternGenerator prioritizes extraction methods in this order for all 6 fields:

**Fields Extracted:**
1. **price** 💰 - Current selling price
2. **title** 📝 - Product name
3. **image** 🖼️ - Primary product image URL
4. **availability** ✅ - Stock status
5. **article_number** 🔢 - Store SKU/item number
6. **model_number** 🏷️ - Manufacturer part number

**Extraction Priority (by confidence):**

1. **JSON-LD** (confidence: 0.95+)
   - Most reliable, structured schema.org data
   - Example: `script[type="application/ld+json"]`
   - Fields: price, title, image, model_number

2. **Meta Tags** (confidence: 0.85-0.95)
   - Open Graph and product-specific tags
   - Example: `<meta property="og:price" content="29.99">`
   - Fields: price, title, image

3. **Semantic CSS** (confidence: 0.80-0.90)
   - IDs, data attributes, semantic classes
   - Example: `.product-price`, `[data-price]`, `[itemprop="sku"]`
   - Fields: price, title, availability, article_number, model_number

4. **XPath** (confidence: 0.70-0.75)
   - Last resort with text matching
   - Example: `//span[contains(@class, 'price')]`
   - Fields: All (fallback only)

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

## Storage

### Production (PriceTracker Integration)

Patterns are stored in **PostgreSQL** via Django ORM:

- **`Pattern` model** - Current patterns per domain
  - `pattern_json` (JSONField) - Full pattern structure
  - `success_rate`, `total_attempts`, `successful_attempts` - Performance metrics
  - `last_validated` - Last test timestamp
  - Foreign key to `Store` model

- **`PatternHistory` model** - Version history
  - `version_number` - Sequential version per pattern
  - `pattern_json` - Pattern snapshot at this version
  - `changed_by` (User FK) - Who made the change
  - `change_reason`, `change_type` - Audit trail
  - `success_rate_at_time` - Performance snapshot

### Standalone Mode (Development/Testing)

The `src/tools/storage.py` module provides SQLite storage for standalone usage:

```python
from ExtractorPatternAgent.src.tools.storage import PatternStorage

storage = PatternStorage()
await storage.save_pattern(pattern_data)
patterns = await storage.list_patterns()
```

**Note:** Production deployments use PostgreSQL via Django ORM, not SQLite.

## Dependencies

Core dependencies:
- `playwright`: Browser automation with stealth capabilities
- `beautifulsoup4`: HTML parsing
- `lxml`: XPath support
- `rich`: Terminal formatting (CLI only)
- `structlog`: Structured logging

**Integration dependencies (PriceTracker):**
- Django ORM (PostgreSQL)
- Celery (async task queue)
- Redis (caching)

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
- See pattern management in Django Admin: `/admin/app/pattern/`
