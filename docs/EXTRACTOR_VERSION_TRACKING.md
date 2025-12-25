# Extractor Version Tracking

This document explains how PriceTracker tracks which version of each extractor was used for price extraction.

## Overview

PriceTracker tracks extractor versions to provide:
- **Debugging**: Know which extractor version extracted each price
- **History**: Track changes to extractors over time
- **Analytics**: Correlate extraction quality with extractor versions
- **Rollback**: Identify when extractor changes caused issues

## Architecture

### Components

1. **`versions.json` Manifest** - Pre-generated manifest with git info for each extractor
2. **Version Generator Script** - Creates/updates the manifest from git history
3. **Git Hook** - Automatically updates manifest when extractors change
4. **Storage Layer** - Reads manifest and creates ExtractorVersion records
5. **Extractor Layer** - Returns module name alongside extraction results

### Why a Manifest File?

The production environment runs in Docker containers that:
- ❌ Don't have git installed
- ❌ Don't have access to `.git/` directory
- ❌ Can't run git commands at runtime

Solution: Generate `versions.json` at development time (where git is available) and include it in the container.

## How It Works

### 1. Development Workflow

When you modify an extractor:

```bash
# Edit extractor
vim ExtractorPatternAgent/generated_extractors/komplett_no.py

# Git add and commit (pre-commit hook auto-updates versions.json)
git add ExtractorPatternAgent/generated_extractors/komplett_no.py
git commit -m "Update komplett.no extractor"
# Hook runs: python scripts/generate_versions_manifest.py
# Hook stages: git add ExtractorPatternAgent/generated_extractors/versions.json
```

The pre-commit hook:
- Detects changed extractors
- Regenerates `versions.json` with latest git info
- Stages the updated manifest

### 2. Manifest Structure

`ExtractorPatternAgent/generated_extractors/versions.json`:

```json
{
  "komplett_no": {
    "module": "komplett_no",
    "domain": "komplett.no",
    "version": "1.1",
    "generated_at": "2025-12-17T16:02:31.859494",
    "confidence": 0.92,
    "commit_hash": "da6184fcc534a7e1b6e9bbe159fc605be9a0ac3b",
    "commit_hash_short": "da6184f",
    "commit_message": "Update komplett.no extractor",
    "commit_author": "Your Name",
    "commit_email": "your@email.com",
    "commit_date": "2025-12-21T23:37:54+01:00"
  },
  ...
}
```

### 3. Runtime Flow

```
Fetch Price (fetcher.py)
  ↓
Extract Data (extractor.py)
  ├─ Returns: (ExtractionResult, "komplett_no")  # Module name
  ↓
Save Price (storage.py)
  ├─ Reads: versions.json manifest
  ├─ Finds: komplett_no version info
  ├─ Creates/Gets: ExtractorVersion record
  │   - commit_hash: da6184f...
  │   - extractor_module: "komplett_no"
  │   - metadata: {version, confidence, etc.}
  ↓
Links to ProductListing.extractor_version_id
```

### 4. Database Schema

**ExtractorVersion Table:**
```sql
CREATE TABLE app_extractorversion (
    id INTEGER PRIMARY KEY,
    commit_hash VARCHAR(40),
    extractor_module VARCHAR(255),
    commit_message TEXT,
    commit_author VARCHAR(200),
    commit_date DATETIME,
    metadata JSON,  -- {version, confidence, domain, etc.}
    created_at DATETIME,
    UNIQUE(commit_hash, extractor_module)
);
```

**ProductListing Link:**
```sql
CREATE TABLE app_productlisting (
    ...
    extractor_version_id INTEGER REFERENCES app_extractorversion(id),
    ...
);
```

## Setup

### One-Time Setup (Per Developer)

Install the git hooks:

```bash
./scripts/setup_hooks.sh
```

This creates a symlink to `scripts/hooks/pre-commit` that auto-updates the manifest.

### Manual Manifest Generation

If you need to regenerate the manifest manually:

```bash
# Generate manifest
python scripts/generate_versions_manifest.py

# Verify it's current
python scripts/generate_versions_manifest.py --verify
```

### CI/CD Integration

**Current:** Manual git hook (must be installed per developer)

**Future:** GitHub Actions workflow to auto-generate manifest:

```yaml
# .github/workflows/update-versions.yml
name: Update Extractor Versions
on:
  push:
    paths:
      - 'ExtractorPatternAgent/generated_extractors/*.py'
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Generate manifest
        run: python scripts/generate_versions_manifest.py
      - name: Commit if changed
        run: |
          git config user.name "github-actions[bot]"
          git add ExtractorPatternAgent/generated_extractors/versions.json
          git diff --cached --quiet || git commit -m "chore: Update extractor versions manifest"
          git push
```

## Querying Version Information

### Get Extractor Version for a Price

```sql
SELECT
    pl.id,
    pl.domain,
    pl.current_price,
    ev.extractor_module,
    ev.commit_hash,
    ev.commit_message,
    ev.commit_author,
    ev.commit_date,
    json_extract(ev.metadata, '$.version') as extractor_version,
    json_extract(ev.metadata, '$.confidence') as confidence
FROM app_productlisting pl
LEFT JOIN app_extractorversion ev ON pl.extractor_version_id = ev.id
WHERE pl.domain = 'komplett.no'
ORDER BY pl.last_checked DESC
LIMIT 10;
```

### Find All Versions of an Extractor

```sql
SELECT
    commit_hash,
    commit_date,
    commit_message,
    json_extract(metadata, '$.version') as version,
    json_extract(metadata, '$.confidence') as confidence
FROM app_extractorversion
WHERE extractor_module = 'komplett_no'
ORDER BY commit_date DESC;
```

### Count Listings Per Extractor Version

```sql
SELECT
    ev.extractor_module,
    ev.commit_hash,
    json_extract(ev.metadata, '$.version') as version,
    COUNT(pl.id) as listing_count
FROM app_extractorversion ev
LEFT JOIN app_productlisting pl ON pl.extractor_version_id = ev.id
GROUP BY ev.extractor_module, ev.commit_hash
ORDER BY listing_count DESC;
```

## Troubleshooting

### Manifest Not Found

```
Warning: versions_manifest_not_found
```

**Solution:** Generate the manifest:
```bash
python scripts/generate_versions_manifest.py
```

### Manifest Out of Date

```
ERROR: versions.json is stale
```

**Solution:**
```bash
python scripts/generate_versions_manifest.py
git add ExtractorPatternAgent/generated_extractors/versions.json
git commit --amend --no-edit
```

### Hook Not Running

If the pre-commit hook isn't auto-updating the manifest:

1. **Check hook is installed:**
   ```bash
   ls -l .git/hooks/pre-commit
   # Should be symlink to scripts/hooks/pre-commit
   ```

2. **Reinstall hook:**
   ```bash
   ./scripts/setup_hooks.sh
   ```

3. **Manual bypass** (not recommended):
   ```bash
   git commit --no-verify  # Skip hooks
   ```

### Extractor Not in Manifest

```
Warning: extractor_not_in_manifest module=komplett_no
```

**Causes:**
- Extractor file doesn't have `PATTERN_METADATA`
- Extractor was added but manifest not regenerated
- Module name mismatch (file: `komplett_no.py` vs domain: `komplett.no`)

**Solution:**
```bash
# Verify extractor has PATTERN_METADATA
grep "PATTERN_METADATA" ExtractorPatternAgent/generated_extractors/komplett_no.py

# Regenerate manifest
python scripts/generate_versions_manifest.py
```

## Future Enhancements

1. **GitHub Actions Integration** - Auto-generate manifest in CI
2. **Version Comparison API** - WebUI endpoint to compare extractor versions
3. **Rollback Tool** - CLI to rollback to previous extractor version
4. **Analytics Dashboard** - Show extraction success rate per extractor version
5. **Stale Detector** - Alert if manifest hasn't been updated in X commits

## Related Files

- `scripts/generate_versions_manifest.py` - Manifest generator
- `scripts/hooks/pre-commit` - Git pre-commit hook
- `scripts/setup_hooks.sh` - Hook installation script
- `PriceFetcher/src/storage.py` - Version tracking implementation
- `PriceFetcher/src/extractor.py` - Module name detection
- `ExtractorPatternAgent/generated_extractors/versions.json` - Version manifest
