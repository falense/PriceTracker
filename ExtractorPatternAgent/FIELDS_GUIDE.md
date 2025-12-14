# Extraction Fields Guide

The pattern generator now extracts **6 fields** from e-commerce product pages:

## Fields Extracted

### 1. **Price** 💰
- Current selling price
- Extracts from: data attributes, CSS classes, JSON data
- Example: `1 990,-` or `1990.00`

### 2. **Title** 📝
- Product name/title
- Extracts from: Open Graph meta tags, H1 headings
- Example: `Bose QuietComfort SC trådløse hodetelefoner, Over-Ear (sort)`

### 3. **Image** 🖼️
- Primary product image URL
- Extracts from: Open Graph meta tags, img elements
- Example: `https://www.komplett.no/img/p/200/1310167.jpg`

### 4. **Availability** ✅
- Stock status/availability
- Extracts from: stock indicators, JSON data
- Example: `Tilgjengelighet: 20+ stk. på lager.` or `In Stock`

### 5. **Article Number** 🔢 (NEW)
- Web store item number (Varenummer/SKU)
- Extracts from: `itemprop="sku"`, "Varenummer" labels
- Example: `1310167`

### 6. **Model Number** 🏷️ (NEW)
- Manufacturer model/part number
- Extracts from: JSON data, product specification tables
- Example: `884367-0900`

## Usage

```bash
# Generate patterns with all 6 fields
uv run generate_pattern.py "https://www.komplett.no/product/1310167/..."
```

## Output Example

```json
{
  "store_domain": "komplett.no",
  "patterns": {
    "price": {
      "primary": {
        "type": "css",
        "selector": "#cash-price-container",
        "attribute": "data-price",
        "confidence": 0.95,
        "sample_value": "1 990,-"
      }
    },
    "title": {
      "primary": {
        "type": "meta",
        "selector": "meta[property='og:title']",
        "attribute": "content",
        "confidence": 0.95,
        "sample_value": "Bose QuietComfort SC..."
      }
    },
    "image": {
      "primary": {
        "type": "meta",
        "selector": "meta[property='og:image:secure_url']",
        "attribute": "content",
        "confidence": 0.95,
        "sample_value": "https://www.komplett.no/img/p/200/1310167.jpg"
      }
    },
    "availability": {
      "primary": {
        "type": "css",
        "selector": ".stockstatus-instock",
        "attribute": "title",
        "confidence": 0.90,
        "sample_value": "Tilgjengelighet: 20+ stk. på lager."
      }
    },
    "article_number": {
      "primary": {
        "type": "css",
        "selector": "[itemprop='sku']",
        "confidence": 0.95,
        "sample_value": "1310167"
      }
    },
    "model_number": {
      "primary": {
        "type": "json",
        "selector": ".buy-button",
        "attribute": "data-initobject",
        "json_path": "trackingData.item_manufacturer_number",
        "confidence": 0.90,
        "sample_value": "884367-0900"
      }
    }
  },
  "metadata": {
    "fields_found": 6,
    "total_fields": 6,
    "overall_confidence": 0.93
  }
}
```

## Extraction Methods

The generator uses multiple strategies:

| Field | Primary Method | Fallback Methods |
|-------|---------------|------------------|
| Price | Data attributes | CSS classes, JSON data |
| Title | Open Graph meta | H1 tag, JSON data |
| Image | Open Graph meta | img elements |
| Availability | Stock icon/text | JSON data |
| Article Number | itemprop="sku" | Label + value pairs |
| Model Number | JSON data | Specification tables |

## Pattern Types

- **`css`**: CSS selector
- **`meta`**: Meta tag (Open Graph, etc.)
- **`json`**: JSON in data attributes (requires parsing)

## Confidence Scores

- **0.95**: Very high (meta tags, semantic markup)
- **0.90**: High (data attributes, JSON)
- **0.85**: Good (semantic CSS classes)
- **0.80**: Fair (common patterns)
- **0.75**: Lower (generic selectors)

## Testing Your Patterns

After generation, validate patterns work correctly:

```bash
python test_extraction.py
```

Expected output: **6/6 fields (100%)**

## Notes

- **Article Number** is the store's internal product ID (SKU)
- **Model Number** is the manufacturer's part/model number
- Norwegian sites often use "Varenummer" for article number
- Model numbers may be in product specifications or JSON tracking data
