#!/bin/bash
#
# Setup git hooks for PriceTracker
#
# This script installs git hooks that automate version tracking for extractors.
# Run this once after cloning the repository.
#
# Usage:
#   ./scripts/setup_hooks.sh
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get repository root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$REPO_ROOT"

echo "Setting up git hooks for PriceTracker..."
echo ""

# Ensure .git/hooks directory exists
mkdir -p .git/hooks

# Install pre-commit hook
HOOK_SOURCE="scripts/hooks/pre-commit"
HOOK_DEST=".git/hooks/pre-commit"

if [ ! -f "$HOOK_SOURCE" ]; then
    echo "ERROR: Hook source not found: $HOOK_SOURCE"
    exit 1
fi

# Backup existing hook if present
if [ -f "$HOOK_DEST" ]; then
    echo -e "${YELLOW}Warning:${NC} Existing pre-commit hook found"
    BACKUP="$HOOK_DEST.backup.$(date +%s)"
    cp "$HOOK_DEST" "$BACKUP"
    echo "  Backed up to: $BACKUP"
fi

# Create symlink to tracked hook file
ln -sf "../../$HOOK_SOURCE" "$HOOK_DEST"
chmod +x "$HOOK_SOURCE"

echo -e "${GREEN}✓${NC} Installed pre-commit hook"
echo ""

# Test that the hook is executable
if [ -x "$HOOK_DEST" ]; then
    echo -e "${GREEN}✓${NC} Hook is executable"
else
    echo -e "${YELLOW}Warning:${NC} Hook may not be executable"
fi

echo ""
echo "Setup complete! The following hooks are now active:"
echo "  • pre-commit: Auto-updates versions.json when extractors change"
echo ""
echo "To bypass hooks for a specific commit (not recommended):"
echo "  git commit --no-verify"

exit 0
