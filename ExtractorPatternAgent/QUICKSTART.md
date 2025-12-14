# Quick Start - Pattern Generator

## Simple Pattern Generation

### Option 1: UV (Recommended - One Command)

```bash
uv run generate_pattern.py "https://example.com/product/123"
```

UV will automatically:
- Install dependencies (playwright, beautifulsoup4, lxml, rich)
- Run the script
- No virtual environment needed!

### Option 2: Virtual Environment

```bash
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install playwright beautifulsoup4 lxml rich
python -m playwright install chromium

# Run
python generate_pattern.py "https://example.com/product/123"
```

## What Happens

1. **Browser Opens** (visible window) and navigates to the URL
2. **Page Loads** with stealth settings to avoid detection
3. **HTML Analysis** extracts patterns for:
   - Price
   - Title
   - Image
   - Availability/Stock
4. **Results Saved** to `{domain}_patterns.json`
5. **Console Output** shows what was found

## Example Output

```
╭──────────────────────────────────────────╮
│ Pattern Generator                        │
│                                          │
│ URL: https://www.komplett.no/product... │
╰──────────────────────────────────────────╯

Fetching page: https://www.komplett.no/...
✓ Page fetched (1103316 bytes)

Analyzing HTML structure...
  → Finding price patterns...
    ✓ Found: #cash-price-container → 1 990,-
  → Finding title patterns...
    ✓ Found: og:title → Bose QuietComfort SC...
  → Finding image patterns...
    ✓ Found: og:image → https://www.komplett.no/img/...
  → Finding availability patterns...
    ✓ Found: .stockstatus-instock → Tilgjengelighet: 20+ stk...

✓ Pattern Generation Complete

Store Domain: komplett.no
Fields Found: 4/4
Confidence: 91%

✓ Patterns saved to: komplett_no_patterns.json
```

## Test the Patterns

```bash
# Validate the generated patterns
python test_extraction.py
```

## Advanced: Using in Your Code

```python
import asyncio
import json
from generate_pattern import generate_patterns

async def main():
    url = "https://www.komplett.no/product/123"
    patterns = await generate_patterns(url)

    # Use patterns
    print(f"Price selector: {patterns['patterns']['price']['primary']['selector']}")

    # Save for later use
    with open('my_patterns.json', 'w') as f:
        json.dump(patterns, f)

asyncio.run(main())
```

## Troubleshooting

**Browser doesn't open:**
- Make sure you installed chromium: `python -m playwright install chromium`

**Page times out:**
- Some sites have strong anti-bot protection
- Try running in non-headless mode (already default in this script)
- May need to add cookies or additional headers

**No patterns found:**
- The script looks for common patterns
- Some sites may need manual pattern creation
- Check the saved HTML to see the actual structure

## Files Generated

- `{domain}_patterns.json` - Extraction patterns
- Console output with full JSON structure
