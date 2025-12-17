# Test Data Samples

This directory contains HTML samples and screenshots for extractor development and testing.

## Structure

```
test_data/
├── komplett_no/
│   ├── sample_20250117_143022/
│   │   ├── page.html          # Rendered HTML content
│   │   ├── page.png           # Full-page screenshot
│   │   └── metadata.json      # Sample metadata
│   └── sample_20250117_150000/
│       └── ...
└── amazon_com/
    └── ...
```

## Creating Samples

Use the `fetch_sample.py` script to create new samples:

```bash
# Fetch a sample from a URL
python scripts/fetch_sample.py https://www.komplett.no/product/1310167

# Specify custom domain (if auto-detection fails)
python scripts/fetch_sample.py <url> --domain komplett.no

# Quiet mode (for scripting)
python scripts/fetch_sample.py <url> --quiet
```

### What Gets Saved

Each sample directory contains:

1. **page.html** - Complete rendered HTML from the page
2. **page.png** - Full-page screenshot (useful for visual analysis)
3. **metadata.json** - Sample metadata including:
   - URL
   - Domain
   - Timestamp
   - Page title
   - File sizes
   - Fetch duration

## Using Samples

Samples are automatically used by:

- **`test_extractor.py`** - For testing extractors against saved HTML
- **Manual analysis** - Open HTML and screenshot to understand page structure

### Testing Against Samples

```bash
# Test against latest sample
python scripts/test_extractor.py komplett.no

# Test against specific sample
python scripts/test_extractor.py komplett.no --sample sample_20250117_143022

# Test against all samples (regression testing)
python scripts/test_extractor.py komplett.no --all-samples
```

## Metadata Format

Example `metadata.json`:

```json
{
  "url": "https://www.komplett.no/product/1310167",
  "domain": "komplett.no",
  "timestamp": "2025-01-17T14:30:22.123456",
  "page_title": "Bose QuietComfort SC trådløse hodetelefoner",
  "html_size": 234567,
  "screenshot_size": 456789,
  "fetch_duration_seconds": 3.45
}
```

## Retention & Cleanup

- **Retention**: Samples are kept indefinitely for regression testing
- **Cleanup**: Old samples can be manually deleted if disk space is a concern
- **Git**: Samples are gitignored (too large, environment-specific)

## Workflow

1. **Fetch sample** - Capture HTML + screenshot from live page
2. **Analyze** - Open `page.html` and `page.png` to understand structure
3. **Create extractor** - Write Python module in `generated_extractors/{domain}.py`
4. **Test** - Run `test_extractor.py` to validate extraction
5. **Iterate** - Update extractor based on test results, re-test

## Best Practices

- **Multiple samples**: Fetch multiple product pages from same domain to handle variations
- **Version variations**: Keep samples when site layout changes for regression testing
- **Representative products**: Choose products with different attributes (in stock, out of stock, with/without images, etc.)
- **Sample naming**: Samples are auto-named with timestamps - no manual naming needed

## Troubleshooting

### Sample fetch fails
- Check URL is accessible
- Verify Playwright is installed: `python -m playwright install chromium`
- Try with `--quiet` flag removed to see detailed error messages

### No samples for domain
Run `fetch_sample.py` first to create samples:
```bash
python scripts/fetch_sample.py <product_url>
```

### Sample HTML is empty or incomplete
- Site may have strong anti-bot protection
- Cookie consent dialogs may be blocking content (script handles common ones)
- Try accessing URL manually to verify it loads
