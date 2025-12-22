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

### Security Notes

Both workflows use:
- `GITHUB_TOKEN` - Built-in token with write permissions for the repository
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
