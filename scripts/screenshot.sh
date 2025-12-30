#!/bin/bash
# Wrapper script to run screenshot.py using PriceFetcher's uv environment
# This ensures Playwright is available since it's already in PriceFetcher's dependencies

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PRICEFETCHER_DIR="$PROJECT_ROOT/PriceFetcher"

# Set CLAUDE_PROJECT_DIR to project root so screenshots are saved there
export CLAUDE_PROJECT_DIR="$PROJECT_ROOT"

# Change to PriceFetcher directory and run with uv
cd "$PRICEFETCHER_DIR" && uv run python "$SCRIPT_DIR/screenshot.py" "$@"
