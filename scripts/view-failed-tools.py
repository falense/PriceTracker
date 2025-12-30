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

    # Group by (command, error) pair and count occurrences
    failure_pairs = Counter()
    for r in records:
        command = r.get("command", "unknown")
        error = r.get("error", "unknown")
        failure_pairs[(command, error)] += 1

    # Get top N by frequency
    top_n = failure_pairs.most_common(n)

    # Print header
    print("Top Failed Bash Commands")
    print("=" * 80)
    print()

    # Print as numbered list: command | error | count
    for i, ((command, error), count) in enumerate(top_n, 1):
        print(f"{i}. [{count:3d}x] {command} | {error}")


if __name__ == "__main__":
    main()
