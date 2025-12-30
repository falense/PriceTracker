# Failed Tool Call Tracking

This project includes automatic tracking of failed Bash tool calls to help identify patterns and debug recurring issues.

## How It Works

- **Hook**: `PostToolUse` hook in `.claude/settings.json` runs after every Bash tool execution
- **Tracking**: `track-failed-tools.py` logs any Bash command with a non-zero exit code
- **Logging**: Failures are recorded in `~/.claude/logs/failed_tools.jsonl` (JSONL format)
- **Stats**: `~/.claude/logs/failed_tools_stats.txt` is auto-generated with sorted frequency report
- **Focus**: Currently tracks Bash failures (can be extended to other tools)

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

✅ Automatic tracking of failed Bash commands
✅ Non-blocking (doesn't interrupt Claude Code execution)
✅ Sorted by frequency for easy pattern identification
✅ Timestamped for debugging
✅ Includes stderr/stdout and exit codes
✅ Minimal performance overhead (5s timeout)
✅ Extensible to other tool types

## Implementation Details

The hook:
1. Runs after every `PostToolUse` event for Bash tools
2. Checks tool_response for non-zero `exit_code`
3. Extracts error message from stderr or stdout
4. Appends to JSONL log file (append-only, safe for concurrent access)
5. Regenerates stats file (shows most common failures first)
6. Exits with code 0 (non-blocking)

The stats generation uses Python's `Counter` to count and sort tool failures by frequency.

## Testing

To manually test the hook:

```bash
# Simulate a hook input with a failed Bash command
cat > /tmp/test_hook.json << 'EOF'
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Bash",
  "tool_response": {
    "exit_code": 1,
    "stderr": "Command failed"
  }
}
EOF

cat /tmp/test_hook.json | python3 scripts/track-failed-tools.py

# View the results
python3 scripts/view-failed-tools.py
```
