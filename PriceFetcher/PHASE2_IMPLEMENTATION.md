# Phase 2: ExtractorVersion Tracking Implementation

## Overview
This phase implements git version tracking and unified operation logging in the PriceFetcher service. The implementation tracks which git commit version of the extractor code was used for each price extraction and logs all operations to a centralized OperationLog table.

## Changes Made

### 1. Git Utilities (`src/git_utils.py`)
New module providing git integration functions:
- `get_current_commit_hash()` - Get current git HEAD commit hash
- `get_commit_info()` - Get detailed commit metadata (author, message, date, branch, tags)

Mirrors functionality from `WebUI/app/utils/git_utils.py` but simplified for PriceFetcher needs.

### 2. Storage Layer Updates (`src/storage.py`)

#### New Methods:
- **`get_or_create_extractor_version(extractor_module, commit_hash)`**
  - Creates or retrieves ExtractorVersion record from database
  - Stores full git commit metadata
  - Returns version ID for linking to listings

- **`log_operation(service, level, event, message, context, ...)`**
  - Logs operations to `app_operationlog` table
  - Supports structured logging with context data
  - Links operations to listings, products, and tasks

#### Modified Methods:
- **`save_price()`**
  - Now tracks `extractor_version_id` on ProductListing records
  - Automatically gets/creates version before saving
  - Logs price save operation to OperationLog
  - Maintains backward compatibility with FetchLog

### 3. Fetcher Updates (`src/fetcher.py`)

Added OperationLog events at key points:

#### Fetch Product Level:
- **fetch_started** - Beginning of product fetch
- **extraction_completed** - After extraction and validation
- **fetch_failed** - When exception occurs

#### Fetch Run Level:
- **fetch_run_completed** - Summary of entire fetch run with statistics

All events include:
- Structured context data (URLs, domains, errors, metrics)
- Duration tracking (milliseconds)
- Proper logging levels (INFO, WARNING, ERROR)

### 4. Test Suite (`tests/test_version_tracking.py`)
Comprehensive tests for:
- Git utilities (commit hash retrieval, commit info parsing)
- ExtractorVersion creation and retrieval
- OperationLog creation with various parameters
- UUID handling (hyphen removal)

## Database Schema

### ExtractorVersion Table
```sql
CREATE TABLE app_extractorversion (
    id INTEGER PRIMARY KEY,
    commit_hash VARCHAR(40) NOT NULL,
    extractor_module VARCHAR(255) NOT NULL,
    commit_message TEXT,
    commit_author VARCHAR(200),
    commit_date DATETIME,
    metadata JSON,  -- {branch, tags}
    created_at DATETIME NOT NULL,
    UNIQUE(commit_hash, extractor_module)
)
```

### OperationLog Table
```sql
CREATE TABLE app_operationlog (
    id INTEGER PRIMARY KEY,
    service VARCHAR(50) NOT NULL,  -- 'fetcher'
    task_id VARCHAR(100),
    listing_id VARCHAR(32),
    product_id VARCHAR(32),
    level VARCHAR(10) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    event VARCHAR(100) NOT NULL,  -- 'fetch_started', 'price_saved', etc.
    message TEXT,
    context JSON,  -- Structured event data
    filename VARCHAR(100),  -- Source file
    timestamp DATETIME NOT NULL,
    duration_ms INTEGER
)
```

### ProductListing Updates
```sql
ALTER TABLE app_productlisting
ADD COLUMN extractor_version_id INTEGER REFERENCES app_extractorversion(id);
```

## Operational Flow

### Price Extraction Flow:
1. **Fetch Start** → Log `fetch_started` event
2. **Get Version** → Get/create ExtractorVersion for current git commit
3. **Extract Data** → Use extractor module to parse HTML
4. **Validate** → Check extraction quality
5. **Log Result** → Log `extraction_completed` event with validation result
6. **Save Price** → Store to PriceHistory with version tracking
7. **Update Listing** → Set `extractor_version_id` on ProductListing
8. **Log Save** → Log `price_saved` event with metadata

### Error Handling:
- Exceptions are logged to OperationLog with full context
- Version tracking failures are non-fatal (logs warning, continues)
- Maintains backward compatibility with FetchLog

## Backward Compatibility

### FetchLog Maintained
- All existing FetchLog writes continue unchanged
- Parallel operation: both FetchLog and OperationLog are populated
- No breaking changes to existing functionality

### Migration Path
- Can run alongside existing code (Phase 1 infrastructure already deployed)
- Future phases will deprecate FetchLog in favor of OperationLog

## Configuration

### Extractor Module Name
Currently hardcoded as `"python_extractor"` in `save_price()`. This can be made configurable in the future if multiple extractor implementations exist.

### Git Repository
- Expects to run inside a git repository
- Falls back gracefully if git is unavailable (logs warning)
- Uses HEAD commit by default

## Testing

Run integration tests:
```bash
cd PriceFetcher
source .venv/bin/activate
python -m pytest tests/test_version_tracking.py -v
```

Manual verification:
```bash
# Check git utilities work
python -c "from src.git_utils import get_current_commit_hash; print(get_current_commit_hash())"
```

## Next Steps (Phase 3)
- Version management UI and analytics dashboard
- Version comparison and diff views
- Performance metrics by version
- Rollback capabilities

## Notes
- All UUIDs are stored without hyphens in SQLite (Django convention)
- Timestamps use Django SQLite format: `YYYY-MM-DD HH:MM:SS.mmmmmm`
- StructLog parameter naming: Use `event_name` instead of `event` to avoid conflicts
