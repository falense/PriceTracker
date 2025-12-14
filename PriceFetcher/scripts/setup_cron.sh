#!/bin/bash
# Setup cron jobs for PriceFetcher

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up PriceFetcher cron jobs..."
echo "Project directory: $PROJECT_DIR"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv package manager not found. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

# Generate crontab entries
CRON_ENTRIES="
# PriceFetcher - Fetch all products due for checking every 15 minutes
*/15 * * * * cd $PROJECT_DIR && uv run scripts/run_fetch.py --all >> logs/cron.log 2>&1

# PriceFetcher - Cleanup old logs daily at 2am
0 2 * * * find $PROJECT_DIR/logs -name '*.log' -mtime +30 -delete
"

echo "Cron entries to be added:"
echo "$CRON_ENTRIES"
echo ""

read -p "Do you want to add these cron jobs? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Add to crontab
    (crontab -l 2>/dev/null || true; echo "$CRON_ENTRIES") | crontab -
    echo "Cron jobs added successfully!"
    echo ""
    echo "To view current cron jobs: crontab -l"
    echo "To remove cron jobs: crontab -e"
else
    echo "Cron jobs not added."
fi
