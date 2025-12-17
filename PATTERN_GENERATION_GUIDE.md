# Pattern Generation Guide

Step-by-step guide for creating extraction patterns for new stores in PriceTracker.

## Overview

PriceTracker uses Python extractor modules to extract product data (price, title, image, etc.) from store websites. This guide covers the complete workflow for adding support for a new store.

## Prerequisites

- Python 3.10+
- Access to the store's product page URL
- ExtractorPatternAgent installed and configured
- PriceTracker WebUI database access

## Workflow Overview

```
1. Generate Python extractor → 2. Test extractor → 3. Register in database → 4. Verify integration
```

---

## Step 1: Generate the Python Extractor Module

### Using ExtractorPatternAgent

The ExtractorPatternAgent automatically generates Python extractor modules by analyzing product pages.

```bash
# Navigate to ExtractorPatternAgent directory
cd ExtractorPatternAgent

# Generate pattern for a new store
python -m src.main --url "https://example-store.com/product/12345"
```

**What this does:**
- Fetches the product page HTML
- Analyzes the page structure using LLM
- Generates a Python module with extraction functions
- Saves to `generated_extractors/{domain}.py`

**Example output:**
```
✓ Fetched HTML (2.3s)
✓ Analyzed page structure
✓ Generated extractor: generated_extractors/example_store_com.py
✓ Fields detected: price, title, image, availability
```

### Manual Generation (Advanced)

If you need more control, you can manually create an extractor:

```bash
# Copy the template
cp generated_extractors/example_com.py generated_extractors/newstore_com.py

# Edit the file and implement extract_* functions
```

See `generated_extractors/README.md` for the extractor API reference.

---

## Step 2: Test the Extractor

### 2.1 Quick Test with Python

```bash
cd ExtractorPatternAgent

python3 << 'EOF'
from generated_extractors import extract_from_html, has_parser
import requests

# Check if extractor exists
domain = "example-store.com"
print(f"Extractor exists: {has_parser(domain)}")

# Test extraction
url = "https://example-store.com/product/12345"
html = requests.get(url).text
results = extract_from_html(domain, html)

print(f"Price: {results.get('price')}")
print(f"Title: {results.get('title')}")
print(f"Image: {results.get('image')}")
print(f"Availability: {results.get('availability')}")
EOF
```

### 2.2 Run Unit Tests

```bash
# Run extractor tests
cd ExtractorPatternAgent
pytest tests/test_extractor_registry.py -v

# Test specific domain
python3 -c "
from generated_extractors import get_parser
parser = get_parser('example-store.com')
print(f'✓ Extractor loaded: {parser.PATTERN_METADATA}')
"
```

### 2.3 Test Multiple Products

Test with 3-5 different product URLs from the same store to ensure robustness:

```bash
python3 << 'EOF'
from generated_extractors import extract_from_html
import requests

test_urls = [
    "https://example-store.com/product/12345",
    "https://example-store.com/product/67890",
    "https://example-store.com/product/abc123",
]

for url in test_urls:
    html = requests.get(url).text
    result = extract_from_html("example-store.com", html)
    print(f"\n{url}")
    print(f"  Price: {result.get('price') or 'MISSING'}")
    print(f"  Title: {result.get('title') or 'MISSING'}")
EOF
```

**Success criteria:**
- ✅ Price extracted for all products
- ✅ Title extracted for all products
- ✅ Image URL extracted (when available)
- ✅ No Python errors/exceptions

---

## Step 3: Register Store and Pattern in Database

### 3.1 Create Store Record

Access Django shell:

```bash
cd WebUI
python3 manage.py shell
```

Create the store:

```python
from app.models import Store

# Create store
store = Store.objects.create(
    domain='example-store.com',
    name='Example Store',
    country='NO',  # ISO country code
    currency='NOK',
    active=True,
    verified=True,
    rate_limit_seconds=2  # Minimum delay between requests
)

print(f"✓ Created store: {store}")
```

### 3.2 Create Pattern Record

```python
from app.models import Pattern

# Create pattern pointing to Python extractor
pattern = Pattern.objects.create(
    domain='example-store.com',
    store=store,
    extractor_module='example_store_com',  # Module name without .py
    pattern_json=None,  # No longer using JSON
)

print(f"✓ Created pattern: {pattern}")
```

**Alternative: Use Pattern Management Service**

```python
from app.pattern_services import PatternManagementService
from django.contrib.auth.models import User

admin_user = User.objects.filter(is_superuser=True).first()

pattern, created = PatternManagementService.create_pattern(
    domain='example-store.com',
    extractor_module='example_store_com',
    user=admin_user,
    change_reason='Initial pattern for Example Store'
)

print(f"{'Created' if created else 'Updated'} pattern: {pattern}")
```

---

## Step 4: Verify Integration

### 4.1 Test via Django Shell

```python
from app.pattern_services import PatternTestService

# Test pattern
result = PatternTestService.test_pattern_against_url(
    url='https://example-store.com/product/12345',
    extractor_module='example_store_com',
    use_cache=False
)

print(f"Success: {result['success']}")
print(f"Extraction: {result['extraction']}")
print(f"Errors: {result['errors']}")
print(f"Warnings: {result['warnings']}")
```

### 4.2 Test via Admin Interface

1. Navigate to Django Admin: `http://localhost:8000/admin/`
2. Go to **Patterns**
3. Find your pattern (example-store.com)
4. Click "Test Pattern" or "Visualize"
5. Verify extraction results

### 4.3 Create Test Product Listing

```python
from app.models import Product, ProductListing, Store
from decimal import Decimal

# Get or create product
product, _ = Product.objects.get_or_create(
    name='Test Product from Example Store',
    defaults={
        'brand': 'Test Brand',
        'canonical_name': 'test product from example store'
    }
)

# Get store
store = Store.objects.get(domain='example-store.com')

# Create listing
listing = ProductListing.objects.create(
    product=product,
    store=store,
    url='https://example-store.com/product/12345',
    current_price=Decimal('99.90'),
    currency='NOK',
    available=True,
    active=True
)

print(f"✓ Created listing: {listing}")
```

### 4.4 Test with PriceFetcher

```bash
cd PriceFetcher

# Test single product fetch
python3 << 'EOF'
import asyncio
from src.fetcher import PriceFetcher
from src.models import Product

async def test_fetch():
    fetcher = PriceFetcher(db_path='../WebUI/db.sqlite3')

    # Create test product object
    product = Product(
        product_id='test-123',
        listing_id='listing-456',
        url='https://example-store.com/product/12345',
        domain='example-store.com',
        priority='normal'
    )

    result = await fetcher.fetch_product(product)

    print(f"Success: {result.success}")
    print(f"Price: {result.extraction.price.value if result.extraction else None}")
    print(f"Errors: {result.error}")

asyncio.run(test_fetch())
EOF
```

---

## Step 5: Production Deployment

### 5.1 Commit Changes

```bash
cd /home/falense/Repositories/PriceTracker

# Add new extractor module
git add ExtractorPatternAgent/generated_extractors/{domain}.py

# Commit
git commit -m "feat: Add extractor for {store-name}

- Generated Python extractor module for {domain}
- Tested with {N} product URLs
- Registered in database"

# Push
git push
```

### 5.2 Deploy to Production

```bash
# Pull changes on production server
git pull

# Reload services (if using systemd/supervisor)
sudo systemctl restart pricetracker-celery
sudo systemctl restart pricetracker-web
```

### 5.3 Monitor Initial Fetches

```bash
# Check operation logs
cd WebUI
python3 manage.py shell << 'EOF'
from app.models import OperationLog, FetchLog

# Recent fetch logs for new store
logs = FetchLog.objects.filter(
    listing__store__domain='example-store.com'
).order_by('-fetched_at')[:10]

for log in logs:
    status = '✓' if log.success else '✗'
    print(f"{status} {log.listing.product.name}: {log.extraction_method}")
EOF
```

---

## Troubleshooting

### Problem: Extractor not found

**Error:** `no_extractor_found`

**Solution:**
1. Verify module name matches domain (normalized):
   ```python
   domain = "www.example-store.com"
   module = domain.replace('www.', '').replace('.', '_').replace('-', '_')
   print(f"Module name: {module}")  # example_store_com
   ```

2. Check file exists:
   ```bash
   ls ExtractorPatternAgent/generated_extractors/{module}.py
   ```

3. Reload extractors:
   ```python
   from generated_extractors import reload_extractors
   reload_extractors()
   ```

### Problem: Price not extracted

**Error:** `price_found=False`

**Solution:**
1. Fetch page manually and inspect HTML
2. Check if price is behind JavaScript rendering
3. Verify CSS selectors in extractor module
4. Test with `extract_price()` function directly:
   ```python
   from bs4 import BeautifulSoup
   from generated_extractors.example_store_com import extract_price

   html = open('test_page.html').read()
   soup = BeautifulSoup(html, 'html.parser')
   price = extract_price(soup)
   print(f"Extracted price: {price}")
   ```

### Problem: Pattern validation fails

**Error:** Validation errors in admin interface

**Solution:**
1. Check extractor returns Decimal for price:
   ```python
   from decimal import Decimal
   assert isinstance(result['price'], Decimal)
   ```

2. Verify all required fields:
   ```python
   required = ['price', 'title']
   for field in required:
       assert result.get(field) is not None, f"Missing {field}"
   ```

### Problem: Database integrity errors

**Error:** Store or Pattern already exists

**Solution:**
```python
# Update existing instead of create
from app.models import Pattern
pattern = Pattern.objects.get(domain='example-store.com')
pattern.extractor_module = 'new_module_name'
pattern.save()
```

---

## Best Practices

### ✅ DO
- Test with at least 3-5 different product URLs before deploying
- Use meaningful module names that match the domain
- Add comments in extractor code for complex selectors
- Set appropriate `rate_limit_seconds` for the store
- Monitor initial fetch success rates

### ❌ DON'T
- Don't test on production database directly
- Don't set rate limits below 1 second (risk of IP ban)
- Don't commit sensitive data (credentials, API keys)
- Don't skip testing - broken extractors affect all products
- Don't use JSON patterns (deprecated)

---

## Reference

### File Locations
- **Extractors**: `ExtractorPatternAgent/generated_extractors/`
- **Database**: `WebUI/db.sqlite3`
- **Models**: `WebUI/app/models.py`
- **Services**: `WebUI/app/pattern_services.py`
- **Fetcher**: `PriceFetcher/src/fetcher.py`

### Useful Commands
```bash
# List all extractors
python3 -c "from generated_extractors import list_available_extractors; print(list_available_extractors())"

# Test extractor
python3 -m pytest ExtractorPatternAgent/tests/test_extractor_registry.py

# Check database patterns
cd WebUI && python3 manage.py shell -c "from app.models import Pattern; print(Pattern.objects.all())"

# View recent fetch logs
cd WebUI && python3 manage.py shell -c "from app.models import FetchLog; [print(f.listing.store.domain, f.success) for f in FetchLog.objects.order_by('-fetched_at')[:10]]"
```

### Documentation Links
- Extractor API: `ExtractorPatternAgent/generated_extractors/README.md`
- Model Reference: `WebUI/app/models.py`
- Architecture: See main task `PriceTracker-u2z` design notes

---

## Need Help?

- Check `ExtractorPatternAgent/generated_extractors/example_com.py` for reference implementation
- Review existing extractors for similar store types
- Check OperationLog for detailed error messages
- Use Beads issue tracker: `bd create --title "Pattern issue: {store}"` --type bug`
