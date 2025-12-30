# Failed Tool Call Tracking

This project includes automatic tracking of failed tool calls to help identify patterns and debug recurring issues.

## How It Works

- **Hook**: `PostToolUse` hook in `.claude/settings.json` runs after every tool execution
- **Tracking**: `track-failed-tools.py` logs any tool with a non-zero exit code
- **Logging**: Failures are recorded in `~/.claude/logs/failed_tools.jsonl` (JSONL format)
- **Stats**: `~/.claude/logs/failed_tools_stats.txt` is auto-generated with sorted frequency report

## Log Format

Each failure is recorded as a JSON object in the JSONL file:

```json
{
  "timestamp": "2025-12-30T13:08:52.749523",
  "tool": "Read",
  "exit_code": 1,
  "error": "File not found"
}
```

## Viewing Failures

Use the utility script to analyze failed tool calls:

```bash
# View statistics and recent failures
python3 scripts/view-failed-tools.py

# Filter by specific tool
python3 scripts/view-failed-tools.py --tool Bash

# View top N recent failures
python3 scripts/view-failed-tools.py --top 20

# Clear all logs
python3 scripts/view-failed-tools.py --clear
```

### Example Output

```
📊 Failed Tool Call Statistics
==================================================
Total failures: 6
Unique tools: 3
First failure: 2025-12-30T13:08:52.749523
Latest failure: 2025-12-30T13:09:04.730267

Sorted by frequency (most common first):
--------------------------------------------------
Bash                    3 ( 50.0%) ██████████
Read                    2 ( 33.3%) ██████
Edit                    1 ( 16.7%) ███

📋 Recent 6 Failures
==================================================
2025-12-30T13:08:52.749523 | Read       (exit   1) | File not found
2025-12-30T13:09:04.591560 | Bash       (exit   1) | Command failed
...
```

## Files

- `scripts/track-failed-tools.py` - Main hook script that logs failures
- `scripts/view-failed-tools.py` - Utility to view and analyze logs
- `.claude/settings.json` - Hook configuration (PostToolUse)
- `~/.claude/logs/failed_tools.jsonl` - Raw failure log (JSONL format)
- `~/.claude/logs/failed_tools_stats.txt` - Human-readable statistics

## Features

✅ Automatic tracking of all failed tool calls
✅ Non-blocking (doesn't interrupt Claude Code execution)
✅ Sorted by frequency for easy pattern identification
✅ Timestamped for debugging
✅ Includes exit codes and error messages
✅ Minimal performance overhead (5s timeout)

## Implementation Details

The hook:
1. Runs after every `PostToolUse` event (all tools)
2. Only logs when `exit_code != 0`
3. Appends to JSONL log file (append-only, safe for concurrent access)
4. Regenerates stats file (shows most common failures first)
5. Exits with code 0 (non-blocking)

The stats generation uses Python's `Counter` to count and sort tool failures by frequency.
