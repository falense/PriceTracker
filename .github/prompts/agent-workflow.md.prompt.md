---
agent: agent
---


 Agent Workflow - Issue Tracker Integration

## Overview
As an AI agent working on this project, I use `bd` (beads) dependency-aware issue tracker to manage work systematically.

## Workflow Steps

### 1. Check for Ready Work
```bash
bd ready
```
- Shows issues with status='open' AND no blocking dependencies
- If no ready work found, all issues are blocked or already claimed
- Use `bd list` to see all issues
- **Note:** Issues with status='in_progress' are already claimed by someone else - do not work on them
- Use `bd dep tree <issue-id>` to understand what's blocking work

### 2. Claim an Issue
When ready work is available:
```bash
bd update <issue-id> --status in_progress --assignee copilot
```

### 3. Understand the Issue
```bash
bd show <issue-id>
```
- Read description and requirements
- Check dependencies: `bd dep tree <issue-id>`
- Review related issues if any

### 4. Execute the Work
- Read relevant files using read_file, semantic_search, or grep_search
- Make necessary code changes using replace_string_in_file or multi_replace_string_in_file
- Run tests if applicable
- Verify changes work as expected

### 5. Update Progress
If work is partially complete but needs pause:
```bash
bd update <issue-id> --description "Updated description with progress notes"
```

### 6. Complete the Issue
When work is fully done:
```bash
bd close <issue-id> --reason "Implemented <summary of what was done>"
```

### 7. Discover New Work
If during work I discover new issues or dependencies:
```bash
# Create new issue
bd create "New issue title" -d "Description" -p 2

# Link dependencies if needed
bd dep add <blocked-issue> <blocking-issue>
```

## Priority Levels
- 0: Critical/Urgent
- 1: High
- 2: Medium (default)
- 3: Low
- 4: Nice to have

## Status Values
- open: Not started, available for work
- in_progress: Currently being worked on **by someone else - do not claim**
- blocked: Cannot proceed due to dependencies
- closed: Completed

## Best Practices
1. Always check `bd ready` at start of session
2. Claim issue before starting work (update to in_progress)
3. Close issues immediately after completing work
4. Create new issues when discovering additional work
5. Use dependencies to track relationships between issues
6. Provide clear close reasons for audit trail

## Integration with Todo List
- Use manage_todo_list for complex multi-step work within a single issue
- bd tracks issues across sessions, todo list tracks steps within current work
- Close todo items as they complete, close bd issue when all work done

## Common Commands Reference
```bash
bd ready                    # Find work to do
bd list                     # See all issues
bd show <id>               # View issue details
bd update <id> --status in_progress  # Claim issue
bd close <id>              # Mark complete
bd dep tree <id>           # Visualize dependencies
bd create "Title" -d "Description" -p 2  # Create new issue
```
