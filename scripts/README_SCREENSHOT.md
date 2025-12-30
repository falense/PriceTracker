# Screenshot Tool

A Playwright-based screenshot tool for capturing web pages that agents can analyze. Supports persistent browser sessions for authenticated screenshots.

## Overview

This tool uses Playwright (via the PriceFetcher's uv environment) to capture screenshots of web pages. It's designed to be used by agents that need to visually inspect web pages, including pages that require authentication.

## Files

- `screenshot.py` - Main screenshot script (Python)
- `screenshot.sh` - Wrapper script that uses PriceFetcher's uv environment (recommended)
- `screenshot-session.sh` - Helper script for easier session management

## Features

- **Basic Screenshots** - Capture any public web page
- **Persistent Sessions** - Save browser sessions (cookies, localStorage, etc.) for authenticated screenshots
- **Interactive Login** - Opens a visible browser for you to log in manually
- **Session Management** - List, reuse, and manage saved sessions
- **Flexible Viewport** - Custom sizes including mobile/tablet viewports
- **Full Page Capture** - Screenshot entire scrollable pages

## Usage

### Basic Usage

```bash
# Take a screenshot of a URL
./scripts/screenshot.sh https://example.com

# Custom output path
./scripts/screenshot.sh https://example.com --output /tmp/my_screenshot.png

# Custom viewport size
./scripts/screenshot.sh https://example.com --width 1920 --height 1080

# Full page screenshot (captures entire scrollable page)
./scripts/screenshot.sh https://example.com --full-page
```

### Authenticated Screenshots (New!)

```bash
# Step 1: Interactive login (opens a visible browser)
./scripts/screenshot.sh --login mysite https://example.com/login

# Step 2: Use the saved session for screenshots
./scripts/screenshot.sh --session mysite https://example.com/dashboard

# List all saved sessions
./scripts/screenshot.sh --list-sessions
```

### Quick Session Management

Use the helper script for simpler session commands:

```bash
# Create a session
./scripts/screenshot-session.sh login mysite https://example.com/login

# Use a session
./scripts/screenshot-session.sh use mysite https://example.com/dashboard

# List sessions
./scripts/screenshot-session.sh list
```

### Options

- `url` - URL to screenshot (required, except for --list-sessions)
- `--output, -o PATH` - Output file path (default: auto-generated in /tmp)
- `--width WIDTH` - Viewport width in pixels (default: 1280)
- `--height HEIGHT` - Viewport height in pixels (default: 720)
- `--full-page` - Capture full scrollable page instead of just viewport
- `--timeout TIMEOUT` - Navigation timeout in milliseconds (default: 30000)
- `--session NAME` - Use a saved browser session for authenticated screenshots
- `--login NAME` - Interactive login mode: opens visible browser to save session
- `--list-sessions` - List all saved browser sessions

### Default Behavior

- Screenshots are saved to `.screenshots/` directory in the project root (not version controlled)
- Filename format: `screenshot_<domain>_<timestamp>.png`
- When using a session: `screenshot_<domain>_<session>_<timestamp>.png`
- Viewport size is 1280x720 by default
- Only captures the visible viewport unless `--full-page` is used
- Waits 1 second after page load for dynamic content to render
- Sessions are stored in `~/.playwright_sessions/`

## Session Management

### How Sessions Work

When you use `--login`, the tool:
1. Opens a visible Chromium browser
2. Navigates to your specified URL
3. Waits for you to log in manually
4. Saves all cookies, localStorage, sessionStorage, etc. when you close the browser
5. Stores the session state in `~/.playwright_sessions/<session_name>/state.json`

When you use `--session`, the tool:
1. Loads the saved session state
2. Launches a headless browser with your authenticated session
3. Takes the screenshot as an authenticated user

### Session Workflow

```bash
# 1. Create a session by logging in interactively
./scripts/screenshot.sh --login github https://github.com/login
# Browser opens → you log in → close browser → session saved

# 2. Use the session for screenshots
./scripts/screenshot.sh --session github https://github.com/settings
./scripts/screenshot.sh --session github https://github.com/notifications --full-page

# 3. List your sessions
./scripts/screenshot.sh --list-sessions

# Output:
# Saved browser sessions:
#   - github (last used: 2025-12-30 13:45:23)
#   - mysite (last used: 2025-12-29 10:15:42)
```

## Using in Agent Workflows

Agents can use this tool to:

1. **Capture a page for analysis**
   ```bash
   ./scripts/screenshot.sh https://example.com/product
   ```

2. **Analyze the screenshot** using the Read tool
   ```
   Read the screenshot at /tmp/screenshot_example_com_20250101_120000.png
   ```

3. **Use different viewport sizes** to test responsive designs
   ```bash
   ./scripts/screenshot.sh https://example.com --width 375 --height 667  # Mobile
   ./scripts/screenshot.sh https://example.com --width 768 --height 1024 # Tablet
   ```

4. **Screenshot authenticated pages**
   ```bash
   # First, user logs in interactively (one time)
   ./scripts/screenshot.sh --login myapp https://myapp.com/login

   # Agent can now screenshot authenticated pages
   ./scripts/screenshot.sh --session myapp https://myapp.com/dashboard
   ./scripts/screenshot.sh --session myapp https://myapp.com/settings
   ```

## Technical Details

- Uses Playwright's Chromium browser in headless mode
- Automatically handles cleanup of browser resources
- Inherits Playwright installation from PriceFetcher's uv environment
- Sets a realistic user agent to avoid bot detection
- Includes proper timeout handling and error reporting

## Requirements

The script requires Playwright, which is already installed in the PriceFetcher environment via uv. The wrapper script (`screenshot.sh`) automatically uses this environment.

If you need to run the Python script directly:
```bash
cd PriceFetcher
uv run python ../scripts/screenshot.py https://example.com
```

## Examples

```bash
# Screenshot a product page
./scripts/screenshot.sh https://www.example-store.com/products/123

# Full page screenshot with custom size
./scripts/screenshot.sh https://www.example.com \
  --width 1920 \
  --height 1080 \
  --full-page \
  --output /tmp/fullpage.png

# Quick mobile viewport screenshot
./scripts/screenshot.sh https://example.com --width 375 --height 667
```
