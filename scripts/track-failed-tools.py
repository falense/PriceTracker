#!/usr/bin/env python3
"""
Track failed tool calls and maintain a sorted log of frequency.

This hook runs after each tool execution. If the tool failed (exit code != 0),
it logs the failure and maintains a sorted frequency report.
"""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

LOG_DIR = Path.home() / ".claude" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

FAILED_TOOLS_LOG = LOG_DIR / "failed_tools.jsonl"
STATS_FILE = LOG_DIR / "failed_tools_stats.txt"


def parse_hook_input():
    """Parse the hook input from stdin."""
    try:
        data = json.load(sys.stdin)
        return data
    except (json.JSONDecodeError, ValueError):
        return {}


def log_failure(tool_name: str, exit_code: int, error_msg: str = ""):
    """Log a failed tool call to the JSONL file."""
    failure_record = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool_name,
        "exit_code": exit_code,
        "error": error_msg.strip(),
    }

    with open(FAILED_TOOLS_LOG, "a") as f:
        f.write(json.dumps(failure_record) + "\n")


def generate_stats():
    """Generate and write a sorted frequency report."""
    if not FAILED_TOOLS_LOG.exists():
        return

    tool_counts = Counter()
    with open(FAILED_TOOLS_LOG) as f:
        for line in f:
            try:
                record = json.loads(line)
                tool_counts[record.get("tool", "unknown")] += 1
            except json.JSONDecodeError:
                continue

    if not tool_counts:
        return

    # Sort by frequency (most common first)
    sorted_tools = tool_counts.most_common()

    with open(STATS_FILE, "w") as f:
        f.write("Failed Tool Call Frequency Report\n")
        f.write("=" * 40 + "\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Total failures: {sum(tool_counts.values())}\n")
        f.write(f"Unique tools: {len(tool_counts)}\n\n")

        f.write("Sorted by frequency (most common first):\n")
        f.write("-" * 40 + "\n")
        for tool, count in sorted_tools:
            percentage = (count / sum(tool_counts.values())) * 100
            f.write(f"{tool:30} {count:4} ({percentage:5.1f}%)\n")


def main():
    hook_input = parse_hook_input()

    # Only process if tool failed (exit_code != 0)
    exit_code = hook_input.get("exit_code", 0)
    if exit_code == 0:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "unknown")
    error_msg = hook_input.get("stdout", "") or hook_input.get("stderr", "")

    log_failure(tool_name, exit_code, error_msg)
    generate_stats()

    # Exit 0 to not block Claude execution
    sys.exit(0)


if __name__ == "__main__":
    main()
