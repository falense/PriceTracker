# PriceTracker Firefox Addon

A Firefox browser extension that allows users to track product prices across any website with bookmark-style toggling.

## Features

- **Bookmark-style toggle**: Click the addon icon to add/remove products from your tracking list
- **Visual feedback**: Icon highlights when a product is already tracked
- **Confirmation dialog**: Asks for confirmation before removing tracked products
- **Configurable priority**: Set default priority (low/normal/high) in addon settings
- **Works on any website**: Not limited to stores with extraction patterns

## Prerequisites

1. **Firefox Browser** (version 109.0 or higher)
2. **PriceTracker WebUI** running on `http://localhost:8000`
3. **Active login session** in the WebUI (in the same Firefox browser)

## Installation

### Option 1: Temporary Installation (Development)

1. Open Firefox and navigate to `about:debugging`
2. Click "This Firefox" in the left sidebar
3. Click "Load Temporary Add-on"
4. Navigate to the `firefox-addon` directory
5. Select the `manifest.json` file
6. The addon will be loaded and appear in your toolbar

**Note**: Temporary addons are removed when you close Firefox.

### Option 2: Permanent Installation (Development)

1. Open Firefox and navigate to `about:config`
2. Search for `xpinstall.signatures.required`
3. Set it to `false` (allows unsigned addons)
4. Package the addon:
   ```bash
   cd firefox-addon
   zip -r ../pricetracker-addon.xpi *
   ```
5. Navigate to `about:addons` in Firefox
6. Click the gear icon → "Install Add-on From File"
7. Select the `pricetracker-addon.xpi` file

## Usage

### Adding a Product

1. Navigate to any product page (e.g., Amazon, eBay, or any online store)
2. Click the PriceTracker icon in your toolbar
3. The popup will show "Track this product"
4. Click "Add to Tracking"
5. The product is now tracked! The icon will turn green/highlighted

### Removing a Product

1. Navigate to a tracked product page
2. Click the PriceTracker icon
3. The popup will show product details
4. Click "Remove from Tracking"
5. Confirm the removal in the dialog
6. The product is untracked and the icon returns to normal

### Configuring Settings

1. Right-click the PriceTracker icon
2. Select "Manage Extension" → "Options"
3. Choose your default priority level:
   - **Low**: Daily price checks
   - **Normal**: Hourly price checks (recommended)
   - **High**: Price checks every 15 minutes
4. Click "Save Settings"

## Testing Checklist

### Backend API Tests

Before testing the addon, verify the backend API is working:

```bash
# 1. Start the Django dev server
cd WebUI
source venv/bin/activate
python manage.py runserver

# 2. Log into the WebUI in Firefox
# Visit http://localhost:8000 and log in

# 3. Test the API endpoints (in a new terminal)
# Get session cookie from Firefox DevTools → Storage → Cookies → sessionid

# Check tracking status (replace SESSION_ID)
curl -H "Cookie: sessionid=SESSION_ID" \
     "http://localhost:8000/api/addon/check-tracking/?url=https://example.com/product"

# Expected: {"success": true, "data": {"is_tracked": false}}
```

### Addon Integration Tests

1. **Not logged in → shows login prompt**
   - Log out of the WebUI
   - Click the addon icon
   - Verify "Please log in" state is shown
   - Click "Open PriceTracker" → WebUI opens in new tab

2. **Logged in + new URL → shows "Add to tracking"**
   - Log into the WebUI
   - Navigate to any product page (e.g., `https://www.amazon.com/some-product`)
   - Click the addon icon
   - Verify "Track this product" state is shown
   - Icon should be gray/inactive

3. **Add product → icon changes to active state**
   - Click "Add to tracking" button
   - Wait for loading state
   - Verify product is added successfully
   - Icon should change to green/active
   - Popup should now show "Product is tracked"

4. **Already tracked → shows product details**
   - Refresh the page or navigate away and back
   - Click the addon icon
   - Verify tracked state is shown with:
     - Product name (or "Product from domain.com (uuid)" placeholder)
     - Current price (or "Price pending...")
     - Priority level
     - Availability status
   - Icon should be green/active

5. **Remove product → shows confirmation → untracked**
   - Click "Remove from Tracking" button
   - Verify confirmation dialog appears
   - Click "Yes, Remove"
   - Wait for loading state
   - Verify product is removed
   - Icon should return to gray/inactive
   - Popup should show "Track this product" state

6. **Settings page → change priority → save → persists**
   - Right-click addon icon → Manage Extension → Options
   - Change default priority to "High"
   - Click "Save Settings"
   - Verify "Settings saved!" message
   - Close and reopen Firefox
   - Check settings again → priority should still be "High"
   - Add a new product → verify it uses "High" priority

7. **Session expires → shows login prompt**
   - Log out of the WebUI
   - Navigate to any product page
   - Click addon icon
   - Verify "Please log in" state is shown

8. **Invalid URL (about:, file:) → addon disabled/error**
   - Navigate to `about:blank`
   - Click addon icon
   - Verify error state: "This extension only works on web pages"

### CORS and CSRF Validation

1. **CORS headers present**:
   - Open Firefox Developer Tools → Network tab
   - Add a product via the addon
   - Check the POST request to `/api/addon/track-product/`
   - Verify response headers include:
     - `Access-Control-Allow-Origin: moz-extension://...`
     - `Access-Control-Allow-Credentials: true`

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
- Check the browser console for errors (F12 → Console)
- Ensure you're logged into the WebUI

### "Not logged in" error when you are logged in

- Clear your browser cookies and log in again
- Check CORS configuration in `WebUI/config/settings.py`
- Verify `django-cors-headers` is installed

### Icons not updating

- Refresh the page after adding/removing products
- Check the background script console:
  - Go to `about:debugging` → This Firefox → PriceTracker → Inspect
  - Look for errors in the console

### API returns 403 Forbidden

- Check CSRF token is being sent (Network tab)
- Verify CORS headers are configured correctly
- Ensure `corsheaders.middleware.CorsMiddleware` is in MIDDLEWARE

## Development

### File Structure

```
firefox-addon/
├── manifest.json          # Extension manifest (Manifest V2)
├── background.js          # API communication, icon updates
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

**Background Script Console:**
- `about:debugging` → This Firefox → PriceTracker → Inspect
- Console shows background.js logs

**Popup Console:**
- Right-click popup → Inspect Element
- Console shows popup.js logs

**Check Addon Errors:**
- `about:debugging` → This Firefox
- Look for errors/warnings under PriceTracker

### Modifying the Addon

After making changes:
1. Go to `about:debugging` → This Firefox
2. Click "Reload" next to PriceTracker
3. Changes will take effect immediately

## Security Notes

- **Session authentication**: Uses Django session cookies
- **CSRF protection**: All POST requests include CSRF token
- **CORS safety**: Only allows `moz-extension://` origins
- **No credentials stored**: Addon doesn't store passwords or tokens

## Future Enhancements

- [ ] Notification badge showing price drop count
- [ ] Quick stats in popup (total tracked, recent drops)
- [ ] Set target price directly in popup
- [ ] Support for custom WebUI URL (self-hosted instances)
- [ ] Context menu: "Track this product" on right-click
- [ ] Bulk tracking from search results

## License

Part of the PriceTracker project.
