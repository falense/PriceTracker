# GitHub Actions Workflows

## Automated Extractor Generation Pipeline

### Overview
This repository has a fully automated workflow for creating web scraper extraction patterns using AI agents. The pipeline handles everything from fetching HTML samples to code review and auto-merge.

### Main Workflow: `generate-extractor.yml`

A comprehensive 3-job pipeline that autonomously generates, reviews, and merges extraction patterns.

**Trigger**: Manual workflow dispatch with product URL
**Duration**: ~8-12 minutes (happy path)
**Output**: Merged Python extractor module in `generated_extractors/`

#### How It Works

**Job 1: Generate Extractor**
1. Extracts domain from provided URL
2. Creates feature branch: `extractor/{domain}`
3. Runs autonomous AI agent (`generate_pattern.py`)
4. Agent fetches HTML sample using Playwright
5. Agent validates sample (fails fast on CAPTCHA/blocking)
6. Agent analyzes HTML structure and generates Python extractor
7. Agent tests extractor against sample data
8. Agent iterates on failures until tests pass
9. Auto-commits extractor to git
10. Pushes branch and creates pull request

**Job 2: Review Agent**
1. Runs `test_extractor.py` to validate extraction
   - Verifies critical fields (price, title, currency) are extracted
   - Calculates success rate across all fields
   - Fails if critical fields are missing
2. Runs Claude Code security review
   - Checks code quality (follows BaseExtractor patterns, has fallbacks)
   - Checks security (no network calls, file access, dangerous imports)
   - Posts approval or rejection comment
3. Approves PR if all checks pass

**Job 3: Auto-Merge**
1. Enables auto-merge (squash) when review approves
2. Posts completion comment with review summary
3. Deletes branch after merge

#### Architecture Diagram

```
User triggers workflow (URL)
    ↓
Job 1: Generate Extractor
  → Create branch: extractor/{domain}
  → Run autonomous agent
  → Create PR
    ↓ (success)
Job 2: Review Agent
  → Test extractor (validate critical fields)
  → Claude Code review (quality + security)
  → Approve if all pass
    ↓ (approved)
Job 3: Auto-Merge
  → Enable auto-merge (squash)
  → Delete branch after merge
    ↓
Merged to main
```

### Usage

#### Generating a New Extractor

1. Go to [Actions tab → Generate Extractor Pattern](../../actions/workflows/generate-extractor.yml)
2. Click "Run workflow"
3. Enter product URL (e.g., `https://www.komplett.no/product/1310167`)
4. Click "Run workflow"
5. Wait ~10 minutes for completion
6. Check the created PR for review details

#### Example URLs

**Known-good URLs** (for testing):
- `https://www.komplett.no/product/1310167` - Norwegian electronics store
- `https://www.power.no/data-og-tilbehoer/pc-tilbehoer/mus/logitech-mx-master-3s-grafitrosa/p-1332264/`

**Will fail** (for testing error handling):
- URLs with CAPTCHA/bot protection
- Sites that block automated access

### Setup Requirements

#### Required Secrets

**`CLAUDE_CODE_OAUTH_TOKEN`** (Required)
- Used by: `generate_pattern.py` (Job 1) and Claude Code review (Job 2)
- Get it from: https://code.claude.com/settings
- How to add:
  1. Go to repository → Settings → Secrets and variables → Actions
  2. Click "New repository secret"
  3. Name: `CLAUDE_CODE_OAUTH_TOKEN`
  4. Value: Paste your token
  5. Click "Add secret"

**`PAT_TOKEN`** (Recommended)
- Used for: PR approval (GITHUB_TOKEN cannot approve own PRs)
- Fallback: Uses `GITHUB_TOKEN` if not set (auto-merge may fail)
- How to create:
  1. Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
  2. Click "Generate new token"
  3. Name: `PriceTracker Workflow Automation`
  4. Repository access: Select "Only select repositories" → Choose `PriceTracker`
  5. Permissions:
     - ✅ **Pull requests**: Read and write
     - ✅ **Contents**: Read and write
  6. Generate token and copy it
  7. Add as repository secret (same steps as above)

### Other Workflows

#### `claude.yml` - Interactive Claude Code
- **Trigger**: Mention `@claude` in issues or PR comments
- **Purpose**: Interactive assistance with development tasks
- No conflict with automated pipeline

#### `claude-code-review.yml` - Manual PR Review
- **Trigger**: PR opened or synchronized (excluding `extractor/*` branches)
- **Purpose**: Reviews manually created PRs
- **Filter**: Skips automated extractor PRs (already reviewed by Job 2)

### Success Criteria

The workflow succeeds when:
- ✅ Extractor is generated from URL
- ✅ Tests pass for critical fields (price, title, currency)
- ✅ Security review passes (no dangerous code)
- ✅ PR is created, approved, and merged
- ✅ Branch is deleted

### Failure Scenarios

| Scenario | Job | Result |
|----------|-----|--------|
| CAPTCHA/Blocking detected | 1 | Job fails, no PR created |
| Invalid URL | 1 | Job fails immediately |
| Network timeout | 1 | Job fails after 30min timeout |
| No extractor created | 1 | Job fails with error |
| Critical fields test fail | 2 | Job fails, PR remains open |
| Security review rejects | 2 | Job fails, PR needs manual fix |
| Auto-merge disabled | 3 | Comment suggests manual merge |

### Troubleshooting

**Workflow fails at Job 1 with "CAPTCHA detected":**
- Site blocks automated access
- Try a different product URL from the same domain
- Some sites cannot be automated

**Workflow fails at Job 2 with "Critical fields failed":**
- Generated extractor couldn't extract price/title/currency
- Check PR for HTML sample and extractor code
- May need manual fixes to selectors

**Auto-merge doesn't complete:**
- Check branch protection rules
- Verify `PAT_TOKEN` secret exists
- Ensure no merge conflicts

**Permission errors:**
- Verify `CLAUDE_CODE_OAUTH_TOKEN` secret exists
- Check `PAT_TOKEN` permissions (pull requests + contents)

### Testing the Workflow

**Test happy path:**
```bash
# Go to Actions tab
# Run workflow with: https://www.komplett.no/product/1310167
# Expected: Full success, PR merged in ~10 minutes
```

**Test blocking detection:**
```bash
# Run workflow with a URL known to have CAPTCHA
# Expected: Job 1 fails with blocking error
```

### Security Notes

The workflow:
- ✅ Validates extracted code for security issues
- ✅ Restricts agent to safe tools (Read, Write, Edit, Bash, Glob, Grep)
- ✅ Checks for dangerous patterns (eval, exec, network calls, file access)
- ✅ Runs tests to ensure extractor works before merge
- ✅ Uses scoped tokens with minimal permissions
- ✅ Fails fast on errors (no silent failures)

### Migration from Old Workflows

**Removed workflows** (replaced by `generate-extractor.yml`):
- ❌ `auto-approve-patterns.yml` - Old approval without review
- ❌ `auto-merge-patterns.yml` - Complex 4-job flow
- ❌ `auto-merge-patterns-no-approval.yml` - Merge without validation

**Why replaced?**
- New workflow provides comprehensive validation (tests + security review)
- Old workflows approved without checking if extractor actually works
- Simplified from multiple workflows to one unified pipeline
