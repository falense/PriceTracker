#!/usr/bin/env python3
"""
Utility to view and analyze failed tool call logs.

Usage:
    python3 view-failed-tools.py [--top N] [--tool TOOL_NAME] [--clear]
"""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

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


def display_stats(records):
    """Display overall statistics."""
    if not records:
        print("No failed tool calls recorded yet.")
        return

    tool_counts = Counter(r["tool"] for r in records)
    total = len(records)

    print("\n📊 Failed Tool Call Statistics")
    print("=" * 50)
    print(f"Total failures: {total}")
    print(f"Unique tools: {len(tool_counts)}")
    print(f"First failure: {records[0]['timestamp']}")
    print(f"Latest failure: {records[-1]['timestamp']}\n")

    print("Sorted by frequency (most common first):")
    print("-" * 50)
    for tool, count in tool_counts.most_common():
        pct = (count / total) * 100
        bar = "█" * int(pct / 5)
        print(f"{tool:20} {count:4} ({pct:5.1f}%) {bar}")


def display_recent(records, limit=10):
    """Display recent failures."""
    if not records:
        return

    print(f"\n📋 Recent {min(limit, len(records))} Failures")
    print("=" * 50)
    for record in records[-limit:]:
        ts = record["timestamp"]
        tool = record["tool"]
        code = record["exit_code"]
        error = record["error"][:50] if record["error"] else "(no error)"
        print(f"{ts} | {tool:10} (exit {code:3}) | {error}")


def filter_by_tool(records, tool_name):
    """Filter records by tool name."""
    return [r for r in records if r["tool"].lower() == tool_name.lower()]


def clear_logs():
    """Clear the log files."""
    if FAILED_TOOLS_LOG.exists():
        FAILED_TOOLS_LOG.unlink()
        print(f"✓ Cleared {FAILED_TOOLS_LOG}")


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else []

    if "--clear" in args:
        clear_logs()
        return

    records = load_failures()

    if "--tool" in args:
        idx = args.index("--tool")
        if idx + 1 < len(args):
            tool_name = args[idx + 1]
            records = filter_by_tool(records, tool_name)
            print(f"\nFiltered to {len(records)} failures for '{tool_name}'")

    display_stats(records)
    display_recent(records, limit=15)


if __name__ == "__main__":
    main()
