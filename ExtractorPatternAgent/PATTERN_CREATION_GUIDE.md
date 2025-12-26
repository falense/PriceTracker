# Pattern Creation & Update Guide

This guide provides step-by-step instructions for creating new extraction patterns or updating existing ones for the PriceTracker system.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Creating a Pattern from Scratch](#creating-a-pattern-from-scratch)
4. [Updating an Existing Pattern](#updating-an-existing-pattern)
5. [Best Practices](#best-practices)
6. [Common Pitfalls](#common-pitfalls)

---

## Overview

Extraction patterns are Python modules that extract product data from e-commerce websites. Each pattern must extract:
- **Required**: `price`, `title`
- **Optional**: `image`, `availability`, `article_number`, `model_number`

Patterns are located in `ExtractorPatternAgent/generated_extractors/` and follow a standardized structure.

### Fields Reference

Each extractor should extract up to **6 fields** from e-commerce product pages:

#### 1. **Price** 💰 (Required)
- Current selling price as a Decimal
- Extracts from: data attributes, CSS classes, JSON-LD, dataLayer
- Example values: `1990.00`, `299.99`
- Example sources: `1 990,-`, `€299,-`

#### 2. **Title** 📝 (Required)
- Product name/title
- Extracts from: Open Graph meta tags, H1 headings, JSON-LD
- Example: `Bose QuietComfort SC trådløse hodetelefoner, Over-Ear (sort)`

#### 3. **Image** 🖼️ (Optional)
- Primary product image URL
- Extracts from: Open Graph meta tags (`og:image`, `og:image:secure_url`), img elements
- Example: `https://www.komplett.no/img/p/200/1310167.jpg`

#### 4. **Availability** ✅ (Optional)
- Stock status/availability information
- Extracts from: stock indicators, availability elements, JSON data
- Example: `50+`, `In Stock`, `Out of Stock`, `Tilgjengelighet: 20+ stk. på lager.`

#### 5. **Article Number** 🔢 (Optional)
- Web store item number (Varenummer/SKU/Product ID)
- Extracts from: `itemprop="sku"`, dataLayer, product specification tables, URLs
- Example: `1310167`

#### 6. **Model Number** 🏷️ (Optional)
- Manufacturer model/part number
- Extracts from: dataLayer, JSON-LD, product specification tables
- Example: `884367-0900`

---

## Prerequisites

### Tools Required
- **uv** (Python package manager)
- **Browser** with developer tools (for inspecting HTML)
- **Terminal** access

### Understanding the Base System
Familiarize yourself with:
- `generated_extractors/_base.py` - Contains `BaseExtractor` utility methods
- `scripts/test_extractor.py` - For testing patterns
- `scripts/fetch_sample.py` - For capturing page samples

---

## Creating a Pattern from Scratch

### Step 1: Fetch Sample Data

Capture HTML snapshots of the target website:

```bash
cd ExtractorPatternAgent
uv run scripts/fetch_sample.py https://example.com/product/12345
```

This creates:
- `test_data/<domain>/sample_<timestamp>/page.html` - Full HTML
- `test_data/<domain>/sample_<timestamp>/page.png` - Screenshot
- `test_data/<domain>/sample_<timestamp>/metadata.json` - Metadata

**Tip**: Fetch multiple samples to ensure pattern works across different products.

### Step 2: Analyze the HTML Structure

Open the HTML file and identify extraction points for each field:

#### A. Check for Structured Data (Priority 1)

Look for these high-reliability sources:

**1. JSON-LD (Schema.org)**
```html
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Product Title",
  "offers": {
    "price": "299.00"
  }
}
</script>
```

**2. OpenGraph Meta Tags**
```html
<meta property="og:title" content="Product Title">
<meta property="og:image" content="https://...">
```

**3. dataLayer (Google Analytics/GTM)**
```javascript
dataLayer.push({
  "productId": "12345",
  "ecomm_prodid": "12345",
  "item_manufacturer_number": "ABC123"
});
```

**4. Data Attributes on Elements**
```html
<div id="price" data-price="299">299,-</div>
<button class="buy-button" data-initobject='{"price":299}'>
```

#### B. Identify CSS Selectors (Priority 2)

Use browser DevTools to find unique selectors:

```bash
# Common price selectors
.product-price, .price-now, #price-container
[itemprop="price"], .price__value

# Common title selectors
h1.product-title, .product-name, [itemprop="name"]
meta[property="og:title"]

# Common availability selectors
.stock-status, .availability, [itemprop="availability"]
.in-stock, .out-of-stock

# Common image selectors
.product-image img, [itemprop="image"]
meta[property="og:image"]
```

#### C. Search for Specific Patterns

Use grep to find patterns in the HTML:

```bash
# Find price-related attributes
grep -i "price\|pris\|cost" test_data/example_com/sample_*/page.html | head -20

# Find product ID/SKU
grep -i "sku\|product.*id\|article.*number" test_data/example_com/sample_*/page.html | head -20

# Find model numbers
grep -i "model\|manufacturer.*number\|part.*number" test_data/example_com/sample_*/page.html | head -20
```

### Step 3: Create the Pattern File

Create `generated_extractors/example_com.py`:

```python
"""
Extractor for example.com

Created on: YYYY-MM-DD
"""
import re
from decimal import Decimal
from typing import Optional
from bs4 import BeautifulSoup
from ._base import BaseExtractor


# Metadata (required for discovery)
PATTERN_METADATA = {
    'domain': 'example.com',
    'created_at': '2025-12-17T12:00:00',
    'created_by': 'manual',
    'version': '1.0',
    'confidence': 0.90,
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number'],
    'notes': 'Initial pattern created manually'
}


def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.
    
    Primary: <describe primary method>
    Confidence: 0.XX
    """
    # PRIMARY SELECTOR - Most reliable
    elem = soup.select_one("#price-container")
    if elem:
        value = elem.get("data-price")
        if value:
            return BaseExtractor.clean_price(value)
    
    # FALLBACK 1 - Second most reliable
    elem = soup.select_one(".product-price")
    if elem:
        return BaseExtractor.clean_price(elem.get_text(strip=True))
    
    # FALLBACK 2 - Last resort
    elem = soup.select_one("meta[itemprop='price']")
    if elem:
        value = elem.get("content")
        if value:
            return BaseExtractor.clean_price(value)
    
    return None


def extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Extract product title."""
    # PRIMARY: OpenGraph
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove noise (category suffix, etc.)
            if value and ' - ' in value:
                value = value.rsplit(' - ', 1)[0].strip()
            return value if value else None
    
    # FALLBACK 1: H1 heading
    elem = soup.select_one("h1.product-title")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value and ' - ' in value:
            value = value.rsplit(' - ', 1)[0].strip()
        return value if value else None
    
    return None


def extract_image(soup: BeautifulSoup) -> Optional[str]:
    """Extract primary product image URL."""
    # PRIMARY: OpenGraph secure image
    elem = soup.select_one("meta[property='og:image:secure_url']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value
    
    # FALLBACK: OpenGraph image
    elem = soup.select_one("meta[property='og:image']")
    if elem:
        value = elem.get("content")
        if value:
            value = str(value).strip()
            if value.startswith('http'):
                return value
    
    return None


def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    """Extract stock availability status."""
    import re
    
    # PRIMARY: Stock status element
    elem = soup.select_one(".stock-status")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            # Extract numeric quantity (e.g., "50+ in stock" -> "50+")
            match = re.search(r'(\d+\+?|>\d+)', value)
            if match:
                return match.group(1)
            # Normalize status keywords
            if re.search(r'in stock|available', value, re.IGNORECASE):
                return "In Stock"
            if re.search(r'out of stock|unavailable', value, re.IGNORECASE):
                return "Out of Stock"
        return value if value else None
    
    return None


def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract store article number (SKU)."""
    import re
    
    # PRIMARY: dataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer' in script.string:
            match = re.search(r'"productId"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()
    
    # FALLBACK: URL extraction
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical:
        url = canonical.get('href', '')
        if url:
            match = re.search(r'/product/(\d+)/', url)
            if match:
                return match.group(1).strip()
    
    return None


def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract manufacturer model/part number."""
    import re
    
    # PRIMARY: dataLayer
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer' in script.string:
            match = re.search(r'"manufacturer_number"\s*:\s*"([^"]+)"', script.string)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
    
    return None
```

### Step 4: Test the Pattern

```bash
uv run scripts/test_extractor.py example.com
```

Expected output:
```
Testing: example.com
Sample: sample_20251217_120000
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field            ┃ Status    ┃ Extracted Value        ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ price            │ ✓ PASS    │ 299                    │
│ title            │ ✓ PASS    │ Product Name           │
│ image            │ ✓ PASS    │ https://...            │
│ availability     │ ✓ PASS    │ 50+                    │
│ article_number   │ ✓ PASS    │ 12345                  │
│ model_number     │ ✓ PASS    │ ABC123                 │
└──────────────────┴───────────┴────────────────────────┘

Summary: 6/6 fields extracted (100.0%)
Critical fields: ✓ Price, ✓ Title
```

### Step 5: Iterate and Refine

If fields fail:

1. **Re-examine the HTML** - Check if selector is correct
2. **Add more fallbacks** - Different selectors for same data
3. **Improve cleaning** - Remove noise, normalize format
4. **Test with multiple samples** - Ensure pattern works across products

---

## Updating an Existing Pattern

### Step 1: Identify the Issue

Run the test to see which fields are failing:

```bash
uv run scripts/test_extractor.py example.com
```

Example output showing failures:
```
│ article_number   │ ✗ FAIL    │ -                      │
│ model_number     │ ✗ FAIL    │ -                      │
```

### Step 2: Fetch Fresh Sample Data

Capture a new sample to analyze:

```bash
uv run scripts/fetch_sample.py https://example.com/product/12345
```

### Step 3: Analyze What Changed or Was Missing

#### Check the Raw HTML

```bash
# Search for the missing data
grep -i "article\|sku\|product.*id" test_data/example_com/sample_*/page.html | head -20
grep -i "model\|manufacturer" test_data/example_com/sample_*/page.html | head -20
```

#### Inspect Structured Data

Look for:
- **dataLayer** objects: `grep "dataLayer.push" page.html`
- **JSON-LD**: `grep "application/ld+json" page.html`
- **Meta tags**: `grep "og:\|product:" page.html`

### Step 4: Update the Extraction Logic

Open the pattern file and update the failing functions:

**Example: Adding article_number extraction**

```python
def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
    """Extract store article number (SKU)."""
    import re
    
    # NEW: Try dataLayer first
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'dataLayer' in script.string:
            match = re.search(r'"productId"\s*:\s*"([^"]+)"', script.string)
            if match:
                return match.group(1).strip()
    
    # EXISTING: URL extraction as fallback
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical:
        url = canonical.get('href', '')
        if url:
            match = re.search(r'/product/(\d+)/', url)
            if match:
                return match.group(1).strip()
    
    return None
```

### Step 5: Clean Noisy Data

If fields extract but contain unwanted text:

**Example: Title has category suffix**
- Before: `"Product Name - Category Name"`
- After: `"Product Name"`

```python
def extract_title(soup: BeautifulSoup) -> Optional[str]:
    elem = soup.select_one("meta[property='og:title']")
    if elem:
        value = elem.get("content")
        if value:
            value = BaseExtractor.clean_text(value)
            # Remove category suffix after last dash
            if value and ' - ' in value:
                value = value.rsplit(' - ', 1)[0].strip()
            return value if value else None
    return None
```

**Example: Availability has prefix**
- Before: `"Tilgjengelighet: 50+ stk. på lager."`
- After: `"50+"`

```python
def extract_availability(soup: BeautifulSoup) -> Optional[str]:
    import re
    
    elem = soup.select_one(".stock-status")
    if elem:
        value = BaseExtractor.clean_text(elem.get_text())
        if value:
            # Remove prefix
            value = re.sub(r'^Tilgjengelighet:\s*', '', value, flags=re.IGNORECASE).strip()
            # Extract just the number
            match = re.search(r'(\d+\+?|>\d+)', value)
            if match:
                return match.group(1)
        return value if value else None
    return None
```

### Step 6: Update Metadata

Increment the version and update fields list:

```python
PATTERN_METADATA = {
    'domain': 'example.com',
    'created_at': '2025-12-17T12:00:00',
    'created_by': 'manual',
    'version': '1.1',  # Incremented from 1.0
    'confidence': 0.95,  # Updated if improved
    'fields': ['price', 'title', 'image', 'availability', 'article_number', 'model_number'],
    'notes': 'Added article_number and model_number extraction from dataLayer'
}
```

### Step 7: Re-test

```bash
uv run scripts/test_extractor.py example.com
```

Verify all fields now pass:
```
Summary: 6/6 fields extracted (100.0%)
Critical fields: ✓ Price, ✓ Title
```

---

## Best Practices

### 1. Selector Priority

Always use selectors in this order:

1. **Structured data** (dataLayer, JSON-LD, OpenGraph) - Most reliable
2. **Data attributes** (`data-price`, `data-product-id`) - Very reliable
3. **Schema.org microdata** (`itemprop="price"`) - Reliable
4. **Semantic CSS classes** (`.product-price`, `.stock-status`) - Moderate
5. **Generic elements** (`h1`, `img`) - Use as last resort

### 2. Data Cleaning

**Always use BaseExtractor methods:**

```python
# Price cleaning
BaseExtractor.clean_price(value)  # Handles: "1,990.50", "€299,-", etc.

# Text cleaning  
BaseExtractor.clean_text(value)   # Removes excess whitespace, normalizes

# JSON field extraction
BaseExtractor.extract_json_field(data, "path.to.field")
```

**Common cleaning patterns:**

```python
# Remove prefixes/suffixes
value = re.sub(r'^Prefix:\s*', '', value, flags=re.IGNORECASE)
value = value.rsplit(' - ', 1)[0]  # Remove last segment after dash

# Extract numbers
match = re.search(r'(\d+\+?|>\d+)', value)
if match:
    return match.group(1)

# Normalize status keywords
if re.search(r'in stock|available', value, re.IGNORECASE):
    return "In Stock"
```

### 3. Multiple Fallbacks

Always provide 2-3 fallback methods:

```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    # Primary: data attribute
    elem = soup.select_one("#price")
    if elem and elem.get("data-price"):
        return BaseExtractor.clean_price(elem.get("data-price"))
    
    # Fallback 1: CSS class
    elem = soup.select_one(".price-value")
    if elem:
        return BaseExtractor.clean_price(elem.get_text())
    
    # Fallback 2: Meta tag
    elem = soup.select_one("meta[itemprop='price']")
    if elem:
        return BaseExtractor.clean_price(elem.get("content"))
    
    return None
```

### 4. Validation

Add basic validation:

```python
# Price sanity check (already in BaseExtractor.clean_price)
if 0 < price < 1_000_000_000:
    return price

# URL validation
if value and value.startswith('http'):
    return value

# Non-empty string check
return value if value else None
```

### 5. Documentation

Document each extraction function:

```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    """
    Extract price.
    
    Primary: #price-container data-price attribute
    Fallback 1: .product-price text content
    Fallback 2: meta[itemprop='price'] content attribute
    
    Confidence: 0.95
    
    Note: Prices are in NOK, format "XXX,-"
    """
```

---

## Common Pitfalls

### 1. Not Cleaning Data

❌ **Bad:**
```python
return elem.get("content")  # Returns "299,-" or "Title - Category"
```

✅ **Good:**
```python
value = elem.get("content")
return BaseExtractor.clean_price(value)  # Returns Decimal(299)
```

### 2. Single Point of Failure

❌ **Bad:**
```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    elem = soup.select_one(".price")
    return BaseExtractor.clean_price(elem.get_text())  # Fails if element not found
```

✅ **Good:**
```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    elem = soup.select_one(".price")
    if elem:
        return BaseExtractor.clean_price(elem.get_text())
    
    # Multiple fallbacks...
    return None
```

### 3. Ignoring Type Hints

❌ **Bad:**
```python
def extract_price(soup):  # Missing type hints
    return "299"  # Returns string instead of Decimal
```

✅ **Good:**
```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
    return BaseExtractor.clean_price("299")  # Returns Decimal
```

### 4. Overly Specific Selectors

❌ **Bad:**
```python
soup.select_one("body > div.container > div.product > span.price")
```

✅ **Good:**
```python
soup.select_one(".product .price")  # More resilient to layout changes
```

### 5. Not Testing with Multiple Samples

Always test with at least 2-3 different products to ensure:
- Selectors work across product types
- Data cleaning handles different formats
- Edge cases are covered (out of stock, no image, etc.)

### 6. Hardcoded Values

❌ **Bad:**
```python
return "In Stock"  # Always returns the same value
```

✅ **Good:**
```python
value = elem.get_text()
if "in stock" in value.lower():
    return "In Stock"
elif "out of stock" in value.lower():
    return "Out of Stock"
return value
```

---

## Testing Checklist

Before considering a pattern complete:

- [ ] All 6 fields extract successfully (or return `None` gracefully)
- [ ] Price returns a `Decimal` number without currency symbols
- [ ] Title is clean (no category suffixes, excess whitespace)
- [ ] Image URL is valid and starts with `http`
- [ ] Availability is normalized ("50+", "In Stock", "Out of Stock")
- [ ] Article number and model number are clean strings
- [ ] Tested with at least 2 different product samples
- [ ] Metadata version updated if modifying existing pattern
- [ ] All extraction functions have docstrings
- [ ] Code uses BaseExtractor utility methods

---

## Quick Reference

### Common Commands

```bash
# Fetch new sample
uv run scripts/fetch_sample.py https://example.com/product/123

# Test pattern
uv run scripts/test_extractor.py example.com

# Search HTML for patterns
grep -i "keyword" test_data/example_com/sample_*/page.html | head -20
```

### BaseExtractor Methods

```python
BaseExtractor.clean_price(text)           # -> Optional[Decimal]
BaseExtractor.clean_text(text)            # -> Optional[str]
BaseExtractor.extract_json_field(data, path)  # -> Optional[Any]
```

### Required Function Signatures

```python
def extract_price(soup: BeautifulSoup) -> Optional[Decimal]:
def extract_title(soup: BeautifulSoup) -> Optional[str]:
def extract_image(soup: BeautifulSoup) -> Optional[str]:
def extract_availability(soup: BeautifulSoup) -> Optional[str]:
def extract_article_number(soup: BeautifulSoup) -> Optional[str]:
def extract_model_number(soup: BeautifulSoup) -> Optional[str]:
```

---

## Example: Real-World komplett.no Pattern

See `generated_extractors/komplett_no.py` for a complete, production-ready example that demonstrates:

- Multiple fallback strategies
- Data cleaning and normalization
- Extracting from dataLayer JSON
- Removing noisy prefixes/suffixes
- Proper type handling
- Comprehensive documentation

Study this pattern as a reference implementation.

---

## Support

If you encounter issues:

1. Check the HTML structure hasn't changed
2. Verify selectors are still valid
3. Review error messages from test output
4. Compare with working patterns (e.g., `komplett_no.py`)
5. Test with fresh samples from the live site

---

**Last Updated**: 2025-12-17
**Version**: 1.0
