# GitHub Actions Workflows

## Auto-approve Pattern PRs

### Overview
This repository has automated workflows to handle pull requests that create or update extraction patterns.

### Workflows

#### `auto-approve-patterns.yml`
Automatically approves and enables auto-merge for PRs that **only** modify files in:
- `ExtractorPatternAgent/generated_extractors/`

**What it does:**
1. ✅ Detects if the PR only contains pattern files
2. ✅ Auto-approves the PR if validation passes
3. ✅ Enables auto-merge (squash merge)
4. ✅ Adds a comment explaining the auto-approval
5. ✅ Deletes the branch after merge

**Requirements:**
- The PR must **only** contain changes to files within `ExtractorPatternAgent/generated_extractors/`
- Any changes to other files will skip auto-approval
- All required status checks must pass before auto-merge completes

#### `auto-merge-patterns.yml` (Alternative)
A more complex workflow with explicit test runs and approval steps.

### Setup Requirements

The workflow requires a **Personal Access Token (PAT)** to approve PRs, as GitHub Actions' default `GITHUB_TOKEN` cannot approve pull requests.

#### Creating and adding a PAT:

1. **Create a Personal Access Token:**
   - Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
   - Click "Generate new token"
   - Name: `PriceTracker Pattern Auto-Approve`
   - Repository access: Select "Only select repositories" → Choose `PriceTracker`
   - Permissions:
     - ✅ **Pull requests**: Read and write
     - ✅ **Contents**: Read and write (for auto-merge and branch deletion)
   - Generate token and copy it

2. **Add the token as a repository secret:**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `PAT_TOKEN`
   - Value: Paste your PAT
   - Click "Add secret"

3. **Optional: Update branch protection rules:**
   - Go to Settings → Branches → Edit your default branch protection
   - Enable "Require status checks to pass before merging"
   - Optional: Uncheck "Require approvals" for pattern-only PRs to allow immediate merge

### Security Notes

The workflow uses:
- `PAT_TOKEN` - Personal Access Token with limited scope to approve PRs and merge
- Falls back to `GITHUB_TOKEN` for comments and other operations
- Limited scope to only pattern files
- Validation that ensures only pattern files are modified

### Example PRs

These workflows are designed to handle PRs like:
- [Add pattern for power.no](https://github.com/falense/PriceTracker/pull/7)
- Any PR that adds new `<domain>.py` files to `ExtractorPatternAgent/generated_extractors/`

### Testing the Workflow

To test the auto-approval workflow:

1. Create a new branch:
   ```bash
   git checkout -b add-pattern-test
   ```

2. Add or modify a pattern file:
   ```bash
   echo "# Test pattern" > ExtractorPatternAgent/generated_extractors/test_example_com.py
   git add ExtractorPatternAgent/generated_extractors/test_example_com.py
   git commit -m "Add test pattern for example.com"
   ```

3. Push and create a PR:
   ```bash
   git push origin add-pattern-test
   gh pr create --title "Test: Add pattern for example.com" --body "Testing auto-approval"
   ```

4. Watch the workflow run and auto-approve the PR

### Disabling Auto-approval

If you need to disable auto-approval temporarily:

1. Delete or rename the workflow file
2. Or add a condition to skip certain PRs (e.g., by label)

### Troubleshooting

**Workflow doesn't trigger:**
- Check that the PR modifies files in `ExtractorPatternAgent/generated_extractors/`
- Verify the workflow file is on the default branch

**Auto-merge doesn't complete:**
- Check that all required branch protection rules are satisfied
- Ensure there are no merge conflicts
- Verify the PR is approved (should happen automatically)

**Permission errors:**
- The workflow requires `contents: write` and `pull-requests: write` permissions
- These are granted via the `permissions` block in the workflow file
