#!/bin/bash
# Script to create a GitHub Copilot agent task for generating a new extraction pattern

set -e

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if URL is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <product-url> [additional-notes]"
    echo ""
    echo "Example:"
    echo "  $0 https://example.com/product/12345"
    echo "  $0 https://example.com/product/12345 'Requires JavaScript rendering'"
    exit 1
fi

PRODUCT_URL="$1"
ADDITIONAL_NOTES="${2:-}"

# Extract domain from URL
DOMAIN=$(echo "$PRODUCT_URL" | sed -E 's|https?://([^/]+).*|\1|')

# Create task description
TASK_DESC=$(cat <<EOF
## Request
Generate a new extraction pattern for products from **$DOMAIN**.

## Product URL
$PRODUCT_URL

## Pattern Generation Steps

Follow the [Pattern Creation Guide](../ExtractorPatternAgent/PATTERN_CREATION_GUIDE.md):

1. **Fetch sample data**
   \`\`\`bash
   cd ExtractorPatternAgent
   uv run scripts/fetch_sample.py $PRODUCT_URL
   \`\`\`

2. **Analyze HTML structure**
   - Check for structured data (JSON-LD, OpenGraph, dataLayer)
   - Identify CSS selectors for required fields
   - Document extraction strategy

3. **Create pattern file**
   - Location: \`ExtractorPatternAgent/generated_extractors/${DOMAIN//./_}.py\`
   - Implement extraction functions for all 6 fields
   - Add multiple fallback strategies

4. **Test the pattern**
   \`\`\`bash
   uv run scripts/test_extractor.py $DOMAIN
   \`\`\`

5. **Verify all fields extract correctly**
   - ✓ price (required)
   - ✓ title (required)
   - ✓ image (optional)
   - ✓ availability (optional)
   - ✓ article_number (optional)
   - ✓ model_number (optional)

## Additional Notes
$ADDITIONAL_NOTES

---

**Reference Documentation**: [PATTERN_CREATION_GUIDE.md](../ExtractorPatternAgent/PATTERN_CREATION_GUIDE.md)
EOF
)

# Create the agent task
echo "Creating GitHub Copilot agent task for pattern generation..."
echo ""
echo "Task: Generate extraction pattern for $DOMAIN"
echo "URL: $PRODUCT_URL"
echo ""

# Use gh agent-task create with the custom pattern agent
echo "$TASK_DESC" | gh agent-task create -F - --custom-agent pattern.agent --follow

echo ""
echo "✓ Agent task created successfully!"
echo "  Domain: $DOMAIN"
echo "  URL: $PRODUCT_URL"
echo "  Agent: pattern.agent (Pattern generator)"
echo ""
echo "The Copilot pattern agent will:"
echo "  1. Fetch and analyze the product page"
echo "  2. Create a Python extractor module"
echo "  3. Test extraction of price, title, image, availability, etc."
echo "  4. Submit a PR with the new pattern"
