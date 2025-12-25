# PriceTracker Chrome Extension

A Chrome/Chromium browser extension that allows users to track product prices across any website with bookmark-style toggling.

## Features

- **Bookmark-style toggle**: Click the extension icon to add/remove products from your tracking list
- **Visual feedback**: Icon highlights when a product is already tracked
- **Confirmation dialog**: Asks for confirmation before removing tracked products
- **Configurable priority**: Set default priority (low/normal/high) in extension settings
- **Works on any website**: Not limited to stores with extraction patterns
- **Manifest V3**: Built with Chrome's latest extension standard

## Prerequisites

1. **Chrome or Chromium-based browser** (Chrome, Edge, Brave, Opera, etc.)
2. **PriceTracker WebUI** running on `http://localhost:8000`
3. **Active login session** in the WebUI (in the same browser)

## Installation

### Development Installation (Unpacked Extension)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in the top-right corner)
3. Click "Load unpacked"
4. Navigate to and select the `chrome-addon` directory
5. The extension will be loaded and appear in your toolbar
6. (Optional) Pin the extension to your toolbar by clicking the puzzle icon

**Note**: The extension will remain installed until you remove it manually.

### Production Installation (Packed Extension)

1. Package the extension:
   ```bash
   cd chrome-addon
   # In Chrome, go to chrome://extensions/
   # Enable Developer mode → Click "Pack extension"
   # Select the chrome-addon directory
   # This creates chrome-addon.crx and chrome-addon.pem
   ```
2. Install the .crx file:
   - Drag and drop `chrome-addon.crx` onto `chrome://extensions/`
   - Click "Add extension" when prompted

**Note**: Chrome Web Store submission requires publisher verification and is beyond the scope of this README.

## Usage

### Adding a Product

1. Navigate to any product page (e.g., Amazon, eBay, or any online store)
2. Click the PriceTracker icon in your toolbar
3. The popup will show "Track this product"
4. Click "Add to Tracking"
5. The product is now tracked! The icon will turn to active state

### Removing a Product

1. Navigate to a tracked product page
2. Click the PriceTracker icon
3. The popup will show product details
4. Click "Remove from Tracking"
5. Confirm the removal in the dialog
6. The product is untracked and the icon returns to normal

### Configuring Settings

1. Right-click the PriceTracker icon → "Options"
   - Or go to `chrome://extensions/` → PriceTracker → "Extension options"
2. Choose your default priority level:
   - **Low**: Daily price checks
   - **Normal**: Hourly price checks (recommended)
   - **High**: Price checks every 15 minutes
3. Click "Save Settings"

## Key Differences from Firefox Version

This Chrome extension is functionally identical to the Firefox version but includes these technical differences:

### Manifest V3 Adaptations

- **Service Worker**: Uses a service worker for background processing instead of a persistent background page
- **Permissions**: Separated permissions and host_permissions for better security
- **Action API**: Uses `chrome.action` instead of `browser_action`
- **Chrome API**: Uses `chrome.*` namespace (also compatible with `browser.*` via polyfill)

### Benefits of Manifest V3

- Better performance and resource usage
- Enhanced security and privacy
- Improved compatibility with modern Chrome features
- Future-proof for upcoming Chrome updates

## Testing Checklist

### Backend API Tests

Before testing the extension, verify the backend API is working:

```bash
# 1. Start the Django dev server
cd WebUI
source venv/bin/activate
python manage.py runserver

# 2. Log into the WebUI in Chrome
# Visit http://localhost:8000 and log in

# 3. Test the API endpoints (in a new terminal)
# Get session cookie from Chrome DevTools → Application → Cookies → sessionid

# Check tracking status (replace SESSION_ID)
curl -H "Cookie: sessionid=SESSION_ID" \
     "http://localhost:8000/api/addon/check-tracking/?url=https://example.com/product"

# Expected: {"success": true, "data": {"is_tracked": false}}
```

### Extension Integration Tests

1. **Not logged in → shows login prompt**
   - Log out of the WebUI
   - Click the extension icon
   - Verify "Please log in" state is shown
   - Click "Open PriceTracker" → WebUI opens in new tab

2. **Logged in + new URL → shows "Add to tracking"**
   - Log into the WebUI
   - Navigate to any product page (e.g., `https://www.amazon.com/some-product`)
   - Click the extension icon
   - Verify "Track this product" state is shown
   - Icon should be inactive

3. **Add product → icon changes to active state**
   - Click "Add to tracking" button
   - Wait for loading state
   - Verify product is added successfully
   - Icon should change to active state
   - Popup should now show "Product is tracked"

4. **Already tracked → shows product details**
   - Refresh the page or navigate away and back
   - Click the extension icon
   - Verify tracked state is shown with:
     - Product name (or placeholder)
     - Current price (or "Price pending...")
     - Priority level
     - Availability status
   - Icon should be active

5. **Remove product → shows confirmation → untracked**
   - Click "Remove from Tracking" button
   - Verify confirmation dialog appears
   - Click "Yes, Remove"
   - Wait for loading state
   - Verify product is removed
   - Icon should return to inactive state
   - Popup should show "Track this product" state

6. **Settings page → change priority → save → persists**
   - Right-click extension icon → Options
   - Change default priority to "High"
   - Click "Save Settings"
   - Verify "Settings saved!" message
   - Close and reopen Chrome
   - Check settings again → priority should still be "High"
   - Add a new product → verify it uses "High" priority

7. **Session expires → shows login prompt**
   - Log out of the WebUI
   - Navigate to any product page
   - Click extension icon
   - Verify "Please log in" state is shown

8. **Invalid URL (chrome://, file:) → extension disabled/error**
   - Navigate to `chrome://extensions/`
   - Click extension icon
   - Verify error state: "This extension only works on web pages"

### CORS and CSRF Validation

1. **CORS headers present**:
   - Open Chrome Developer Tools → Network tab
   - Add a product via the extension
   - Check the POST request to `/api/addon/track-product/`
   - Verify response headers include appropriate CORS headers

2. **CSRF token sent**:
   - Check the same POST request
   - Verify request headers include:
     - `X-CSRFToken: <token-value>`

3. **Session authentication works**:
   - All API requests should succeed with status 200
   - No 401/403 errors when logged in

## Troubleshooting

### "Failed to connect to PriceTracker"

- Verify the WebUI is running on `http://localhost:8000`
- Open Chrome DevTools (F12) → Console tab for errors
- Ensure you're logged into the WebUI

### "Not logged in" error when you are logged in

- Clear your browser cookies and log in again
- Check CORS configuration in `WebUI/config/settings.py`
- Verify `django-cors-headers` is installed

### Icons not updating

- Refresh the page after adding/removing products
- Check the service worker console:
  - Go to `chrome://extensions/` → PriceTracker → "service worker" link
  - Look for errors in the console

### API returns 403 Forbidden

- Check CSRF token is being sent (Network tab)
- Verify CORS headers are configured correctly
- Ensure `corsheaders.middleware.CorsMiddleware` is in MIDDLEWARE

### Extension not loading

- Check `chrome://extensions/` for errors
- Ensure all files are present in the chrome-addon directory
- Verify manifest.json is valid JSON
- Try reloading the extension

## Development

### File Structure

```
chrome-addon/
├── manifest.json          # Extension manifest (Manifest V3)
├── background.js          # Service worker: API communication, icon updates
├── popup/
│   ├── popup.html        # Popup UI (4 states)
│   ├── popup.js          # State management
│   └── popup.css         # Styling
├── options/
│   ├── options.html      # Settings page
│   ├── options.js        # Settings logic
│   └── options.css       # Settings styling
├── icons/
│   ├── icon-*.png        # Inactive state icons
│   └── icon-*-active.png # Active (tracked) state icons
└── README.md             # This file
```

### Debugging

**Service Worker Console:**
- `chrome://extensions/` → PriceTracker → "service worker" link
- Console shows background.js logs
- Note: Service workers can stop when idle and restart when needed

**Popup Console:**
- Right-click popup → Inspect
- Console shows popup.js logs

**Check Extension Errors:**
- `chrome://extensions/` → Look for errors under PriceTracker

### Modifying the Extension

After making changes:
1. Go to `chrome://extensions/`
2. Click the reload icon (circular arrow) on the PriceTracker card
3. Changes will take effect immediately

### Service Worker Lifecycle

Chrome's Manifest V3 uses service workers that:
- Start on demand (events, messages, alarms)
- Stop when idle to save resources
- Automatically restart when needed
- Cannot use persistent state (use chrome.storage instead)

## Security Notes

- **Session authentication**: Uses Django session cookies
- **CSRF protection**: All POST requests include CSRF token
- **CORS safety**: Configured for extension origins
- **No credentials stored**: Extension doesn't store passwords or tokens
- **Manifest V3 security**: Enhanced privacy and permission controls

## Browser Compatibility

This extension is compatible with:
- Google Chrome (version 88+)
- Microsoft Edge (version 88+)
- Brave Browser
- Opera (version 74+)
- Other Chromium-based browsers supporting Manifest V3

## Future Enhancements

- [ ] Notification badge showing price drop count
- [ ] Quick stats in popup (total tracked, recent drops)
- [ ] Set target price directly in popup
- [ ] Support for custom WebUI URL (self-hosted instances)
- [ ] Context menu: "Track this product" on right-click
- [ ] Bulk tracking from search results
- [ ] Omnibox integration for quick search

## License

Part of the PriceTracker project.
