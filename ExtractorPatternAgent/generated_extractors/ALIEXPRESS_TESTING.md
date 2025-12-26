# AliExpress Extractor - Testing Guide

## Overview

The AliExpress extractor (`aliexpress_com.py`) has been created and tested with mock data. AliExpress has strong anti-bot protection, but the **enhanced fetcher now includes multiple anti-detection measures** to improve success rates.

## Enhanced Fetcher Features

The fetch_sample.py script now includes multiple anti-detection measures:

✅ **Human-like behavior simulation**
- Random mouse movements
- Natural scrolling patterns
- Variable timing delays (3-5 seconds for page load)

✅ **CAPTCHA detection and handling**
- Automatic detection of CAPTCHA and bot-blocking pages
- Manual solving support with non-headless mode
- 30-second wait for user interaction when CAPTCHA detected

✅ **Improved stealth**
- Longer page load times (90s timeout)
- Network idle waiting
- Random delays between actions (500-1500ms initial, 1000-2000ms between steps)

✅ **Non-headless mode**
- Run with visible browser for sites that detect headless mode
- Allows manual CAPTCHA solving and interaction

## Limitations

Despite these enhancements, AliExpress employs very aggressive bot detection:

⚠️ **Geographic/IP-based blocking**
- Data center IPs are often blocked immediately
- Some product URLs may not be accessible from certain regions
- Products may show 404 errors even when valid

⚠️ **Advanced fingerprinting**
- Detects automated browsers through multiple signals
- Canvas fingerprinting, WebGL, and audio context checks
- Timing analysis and behavioral patterns

⚠️ **Session-based restrictions**
- Requires cookies from authenticated sessions
- First-time visits are heavily scrutinized

## Recommended Approach

### Option 1: Non-Headless Mode with Manual Intervention (Best Success Rate)

```bash
cd ExtractorPatternAgent

# Run with visible browser
uv run scripts/fetch_sample.py https://www.aliexpress.com/item/1005003413514494.html --no-headless
```

**What to do when the browser opens:**
1. Wait for page to load
2. If CAPTCHA appears: Solve it manually within 30 seconds
3. If 404 error: The product may be unavailable or geo-blocked
4. Script will automatically capture the page after waiting

### Option 2: Use Different Product URLs

Try multiple product URLs as some may be less restricted:

```bash
# Try different products
uv run scripts/fetch_sample.py https://www.aliexpress.com/item/32854221866.html --no-headless
uv run scripts/fetch_sample.py https://www.aliexpress.com/item/4000055907920.html --no-headless
```

### Option 3: Authenticated Session (Most Reliable)

For production use, the most reliable approach is:

1. **Create an AliExpress account** and log in via regular browser
2. **Export cookies** from your browser session
3. **Inject cookies** into the fetcher (requires code modification)
4. **Use residential proxies** to avoid IP-based blocking

### Option 4: Manual HTML Capture (When All Else Fails)

If automated fetching continues to fail:

1. Open the product page in a regular browser
2. Solve any CAPTCHAs manually
3. Open Developer Tools (F12)
4. Run: `copy(document.documentElement.outerHTML)`
5. Save to `test_data/aliexpress_com/sample_manual/page.html`
6. Test extractor: `uv run scripts/test_extractor.py aliexpress.com --sample sample_manual`

## Testing the Extractor

Once you have real HTML (from enhanced fetcher or manual capture):

```bash
cd ExtractorPatternAgent
uv run scripts/test_extractor.py aliexpress.com
```

Expected output with real HTML:
```
Testing: aliexpress.com
Sample: sample_TIMESTAMP
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field            ┃ Status    ┃ Extracted Value         ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ price            │ ✓ PASS    │ 29.99                   │
│ title            │ ✓ PASS    │ Product Name Here       │
│ image            │ ✓ PASS    │ https://...             │
│ availability     │ ✓ PASS    │ 100+                    │
│ article_number   │ ✓ PASS    │ 1005003413514494        │
│ model_number     │ ✓ PASS    │ MODEL-123               │
└──────────────────┴───────────┴─────────────────────────┘

Summary: 6/6 fields extracted (100.0%)
Critical fields: ✓ Price, ✓ Title
```

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
