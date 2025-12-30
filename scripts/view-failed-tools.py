#!/usr/bin/env python3
"""
View the top N most common failed Bash commands.

Usage:
    python3 view-failed-tools.py [N]

    Default N is 10. Examples:
    - python3 view-failed-tools.py      # Show top 10
    - python3 view-failed-tools.py 5    # Show top 5
    - python3 view-failed-tools.py 20   # Show top 20
"""

import json
import sys
from pathlib import Path
from collections import Counter

LOG_DIR = Path.home() / ".claude" / "logs"
FAILED_TOOLS_LOG = LOG_DIR / "failed_tools.jsonl"


def load_failures():
    """Load all failure records from the JSONL file."""
    if not FAILED_TOOLS_LOG.exists():
        return []

    records = []
    with open(FAILED_TOOLS_LOG) as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def main():
    # Parse command line argument for number of items
    n = 10
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            print("Usage: python3 view-failed-tools.py [N]", file=sys.stderr)
            sys.exit(1)

    records = load_failures()

    if not records:
        return

    # Count failures by error message
    error_counts = Counter(r.get("error", "unknown") for r in records)

    # Get top N
    top_n = error_counts.most_common(n)

    # Print as numbered list
    for i, (error, count) in enumerate(top_n, 1):
        print(f"{i}. {error}")


if __name__ == "__main__":
    main()
