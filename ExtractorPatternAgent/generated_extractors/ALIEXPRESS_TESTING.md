# AliExpress Extractor - Testing Guide

## Overview

The AliExpress extractor (`aliexpress_com.py`) has been created but cannot be fully tested via automated fetching due to AliExpress's strong anti-bot protection (CAPTCHA).

## The Challenge

When attempting to fetch AliExpress product pages programmatically, you will encounter:
- CAPTCHA challenges
- "Unusual traffic" detection
- Slider verification requirements

## Extractor Implementation

The extractor has been designed based on AliExpress's known HTML structure:

### Primary Extraction Method: window.runParams
AliExpress stores all product data in a JavaScript object called `window.runParams`. This is the most reliable extraction source.

```javascript
window.runParams = {
    data: {
        priceModule: {
            minAmount: { value: 29.99, currency: "USD" },
            formattedPrice: "$29.99"
        },
        titleModule: {
            subject: "Product Title Here"
        },
        imageModule: {
            imagePathList: ["//image-url.jpg"]
        },
        quantityModule: {
            totalAvailQuantity: 100
        },
        productId: "1005003413514494"
    }
};
```

### Extraction Strategy

Each field has multiple fallback methods:

1. **Price**: runParams → OpenGraph meta → display elements
2. **Title**: runParams → OpenGraph → H1 → title tag
3. **Image**: runParams imagePathList → OpenGraph → main image element
4. **Availability**: runParams totalAvailQuantity → stock elements
5. **Article Number**: runParams productId → URL extraction
6. **Model Number**: runParams specs → specification tables
7. **Currency**: runParams currency → meta tags → default USD

## Manual Testing Options

### Option 1: Browser Developer Tools

1. Open the AliExpress product URL in a real browser
2. Solve any CAPTCHAs manually
3. Once the page loads, open Developer Tools (F12)
4. Go to Console and run: `document.documentElement.outerHTML`
5. Copy the HTML output
6. Save to `test_data/aliexpress_com/sample_manual/page.html`
7. Run: `uv run scripts/test_extractor.py aliexpress.com --sample sample_manual`

### Option 2: Browser Extension (Save Complete Page)

1. Install a "Save Complete Page" browser extension
2. Navigate to an AliExpress product page
3. Solve CAPTCHAs if needed
4. Use the extension to save the complete HTML
5. Place in `test_data/aliexpress_com/sample_manual/page.html`
6. Test the extractor

### Option 3: Authenticated Session

If you have AliExpress authentication cookies:

1. Modify `fetch_sample.py` to include your session cookies
2. Re-fetch the sample with authenticated session
3. Test the extractor

## Testing with Sample Data

To test the extractor once you have real HTML:

```bash
cd ExtractorPatternAgent
uv run scripts/test_extractor.py aliexpress.com --sample sample_manual
```

Expected output with real HTML:
```
Testing: aliexpress.com
Sample: sample_manual
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field            ┃ Status    ┃ Extracted Value        ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ price            │ ✓ PASS    │ 29.99                  │
│ title            │ ✓ PASS    │ Product Name Here      │
│ image            │ ✓ PASS    │ https://...            │
│ availability     │ ✓ PASS    │ 100+                   │
│ article_number   │ ✓ PASS    │ 1005003413514494       │
│ model_number     │ ✓ PASS    │ MODEL-123              │
└──────────────────┴───────────┴────────────────────────┘

Summary: 6/6 fields extracted (100.0%)
Critical fields: ✓ Price, ✓ Title
```

## Creating a Mock Sample for Testing

If you want to test the extractor logic without a real page, create a minimal HTML file:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Test Product - AliExpress</title>
    <meta property="og:title" content="Test AliExpress Product">
    <meta property="og:image" content="https://example.com/image.jpg">
    <meta property="og:url" content="https://www.aliexpress.com/item/1005003413514494.html">
</head>
<body>
    <script>
    window.runParams = {
        data: {
            priceModule: {
                minAmount: {
                    value: 29.99,
                    currency: "USD"
                },
                formattedPrice: "$29.99"
            },
            titleModule: {
                subject: "Test AliExpress Product Title"
            },
            imageModule: {
                imagePathList: ["//ae01.alicdn.com/kf/H123456/image.jpg"]
            },
            quantityModule: {
                totalAvailQuantity: 150
            },
            productId: "1005003413514494",
            specsModule: {
                props: [
                    {
                        attrName: "Model Number",
                        attrValue: "TEST-MODEL-001"
                    }
                ]
            }
        }
    };
    </script>
</body>
</html>
```

Save this to `test_data/aliexpress_com/sample_mock/page.html` and test.

## Confidence Levels

- **Price extraction**: 0.85 (high - runParams is reliable)
- **Title extraction**: 0.90 (very high - multiple good sources)
- **Image extraction**: 0.85 (high - imagePathList is standard)
- **Availability**: 0.80 (good - but format may vary)
- **Article number**: 0.90 (very high - productId is consistent)
- **Model number**: 0.70 (moderate - depends on seller data)
- **Currency**: 0.90 (very high - always present)

## Known Limitations

1. **Anti-bot protection**: Cannot fetch pages automatically
2. **Dynamic pricing**: Prices may vary by region/currency/login status
3. **Model numbers**: Not all sellers provide model numbers
4. **Variants**: The extractor gets the default variant; multi-variant products may need special handling

## Production Use

For production use with AliExpress:
- Use authenticated sessions with cookies
- Implement CAPTCHA solving service (2captcha, Anti-Captcha)
- Use residential proxies to avoid detection
- Add delays between requests
- Respect rate limits

## Support

If the extractor fails with real HTML:
1. Check if `window.runParams` is present in the HTML
2. Verify the JSON structure hasn't changed
3. Look at console errors in the test output
4. Update selectors/paths if AliExpress changed their structure

## Version History

- **v1.0** (2025-12-26): Initial implementation based on known structure
