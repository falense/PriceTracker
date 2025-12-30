#!/usr/bin/env python3
"""
Track failed Bash tool calls and maintain a sorted log of frequency.

This hook runs after PostToolUse events. It checks the tool_response
for Bash commands that failed (non-zero exit code).
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
DEBUG_LOG = LOG_DIR / "track_failed_tools_debug.log"


def debug(msg: str):
    """Write debug message."""
    with open(DEBUG_LOG, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def parse_hook_input():
    """Parse the hook input from stdin."""
    try:
        data = json.load(sys.stdin)
        debug(f"Parsed hook input: tool_name={data.get('tool_name')}, event={data.get('hook_event_name')}")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        debug(f"Failed to parse JSON: {e}")
        return {}


def is_bash_failed(tool_response: dict) -> tuple:
    """
    Check if a Bash tool execution failed.

    PostToolUse includes returnCodeInterpretation when Bash exits with non-zero code.
    Returns: (is_failed: bool, error_msg: str)
    """
    if not isinstance(tool_response, dict):
        return False, ""

    # returnCodeInterpretation field indicates non-zero exit code
    rci = tool_response.get("returnCodeInterpretation")
    if rci:
        debug(f"Detected failure via returnCodeInterpretation: {rci}")
        return True, rci

    return False, ""


def log_failure(tool_name: str, command: str = "", error_msg: str = ""):
    """Log a failed tool call to the JSONL file."""
    failure_record = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool_name,
        "command": command.strip()[:500],  # Limit command length
        "error": error_msg.strip()[:200],  # Limit error length
    }

    with open(FAILED_TOOLS_LOG, "a") as f:
        f.write(json.dumps(failure_record) + "\n")

    debug(f"Logged failure: {command} -> {error_msg}")


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
    debug("Hook invoked")

    hook_input = parse_hook_input()

    # Only process Bash tool calls
    tool_name = hook_input.get("tool_name", "")
    debug(f"Tool name: {tool_name}")

    if tool_name != "Bash":
        debug(f"Skipping non-Bash tool: {tool_name}")
        sys.exit(0)

    # Check if the Bash command failed
    tool_response = hook_input.get("tool_response", {})
    debug(f"Tool response: {json.dumps(tool_response)}")

    is_failed, error_msg = is_bash_failed(tool_response)
    debug(f"Is failed: {is_failed}, error: {error_msg}")

    if not is_failed:
        debug("Command succeeded, not logging")
        sys.exit(0)

    # Extract the command that was run
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "unknown")
    debug(f"Command: {command}")

    log_failure(tool_name, command, error_msg)
    generate_stats()

    # Exit 0 to not block Claude execution
    sys.exit(0)


if __name__ == "__main__":
    main()
