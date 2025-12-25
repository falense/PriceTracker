/**
 * PriceTracker Chrome Extension - Background Service Worker
 *
 * Handles:
 * - API communication with Django backend
 * - CSRF token management
 * - Icon state updates based on tracking status
 * - Tab change detection
 */

// Configuration
const API_BASE = 'http://localhost:8000';

// Cache for tracking status per tab (reduces API calls)
const tabTrackingCache = new Map();

/**
 * Get CSRF token from Django cookies
 * @returns {Promise<string|null>} CSRF token or null if not found
 */
async function getCsrfToken() {
  try {
    // Method 1: Try to read from cookie
    const cookie = await chrome.cookies.get({
      url: API_BASE,
      name: 'csrftoken'
    });

    if (cookie && cookie.value) {
      return cookie.value;
    }

    // Method 2: Fetch from API endpoint
    const response = await fetch(`${API_BASE}/api/addon/csrf-token/`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    if (response.ok) {
      const data = await response.json();
      return data.data.csrf_token;
    }

    console.error('[PriceTracker] Failed to get CSRF token:', response.status);
    return null;

  } catch (error) {
    console.error('[PriceTracker] Error getting CSRF token:', error);
    return null;
  }
}

/**
 * Check if a URL is being tracked by the current user
 * @param {string} url - The URL to check
 * @returns {Promise<Object|null>} Tracking status object or null on error
 */
async function checkTracking(url) {
  try {
    const encodedUrl = encodeURIComponent(url);
    const response = await fetch(`${API_BASE}/api/addon/check-tracking/?url=${encodedUrl}`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    });

    if (response.status === 401 || response.status === 403) {
      // Not logged in
      return { success: false, error: 'not_logged_in' };
    }

    if (!response.ok) {
      console.error('[PriceTracker] Failed to check tracking:', response.status);
      return null;
    }

    const data = await response.json();
    return data;

  } catch (error) {
    console.error('[PriceTracker] Error checking tracking:', error);
    return null;
  }
}

/**
 * Add a product to user's tracking list
 * @param {string} url - Product URL
 * @param {number} priority - Priority level (1=low, 2=normal, 3=high)
 * @returns {Promise<Object|null>} Response data or null on error
 */
async function trackProduct(url, priority = 2) {
  try {
    const csrfToken = await getCsrfToken();
    if (!csrfToken) {
      return { success: false, error: 'csrf_token_missing' };
    }

    const response = await fetch(`${API_BASE}/api/addon/track-product/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({ url, priority })
    });

    if (response.status === 401 || response.status === 403) {
      return { success: false, error: 'not_logged_in' };
    }

    if (!response.ok) {
      const errorData = await response.json();
      console.error('[PriceTracker] Failed to track product:', errorData);
      return errorData;
    }

    const data = await response.json();
    return data;

  } catch (error) {
    console.error('[PriceTracker] Error tracking product:', error);
    return { success: false, error: 'network_error' };
  }
}

/**
 * Remove a product from user's tracking list
 * @param {string} url - Product URL
 * @returns {Promise<Object|null>} Response data or null on error
 */
async function untrackProduct(url) {
  try {
    const csrfToken = await getCsrfToken();
    if (!csrfToken) {
      return { success: false, error: 'csrf_token_missing' };
    }

    const response = await fetch(`${API_BASE}/api/addon/untrack-product/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify({ url })
    });

    if (response.status === 401 || response.status === 403) {
      return { success: false, error: 'not_logged_in' };
    }

    if (!response.ok) {
      const errorData = await response.json();
      console.error('[PriceTracker] Failed to untrack product:', errorData);
      return errorData;
    }

    const data = await response.json();
    return data;

  } catch (error) {
    console.error('[PriceTracker] Error untracking product:', error);
    return { success: false, error: 'network_error' };
  }
}

/**
 * Update action icon based on tracking status
 * @param {number} tabId - Tab ID
 * @param {boolean} isTracked - Whether the product is tracked
 */
async function updateIcon(tabId, isTracked) {
  try {
    const iconPrefix = 'icon';
    const iconSuffix = isTracked ? '-active' : '';

    await chrome.action.setIcon({
      tabId: tabId,
      path: {
        16: `icons/${iconPrefix}-16${iconSuffix}.png`,
        32: `icons/${iconPrefix}-32${iconSuffix}.png`
      }
    });

    // Update title
    const title = isTracked
      ? 'PriceTracker - Product is tracked'
      : 'PriceTracker - Track this product';

    await chrome.action.setTitle({
      tabId: tabId,
      title: title
    });

  } catch (error) {
    console.error('[PriceTracker] Error updating icon:', error);
  }
}

/**
 * Check tracking status for a tab and update icon
 * @param {number} tabId - Tab ID
 * @param {string} url - Tab URL
 */
async function checkAndUpdateIcon(tabId, url) {
  // Skip internal/invalid URLs
  if (!url || !url.startsWith('http://') && !url.startsWith('https://')) {
    // Reset to default inactive icon
    updateIcon(tabId, false);
    tabTrackingCache.delete(tabId);
    return;
  }

  // Check if we have a cached result
  const cached = tabTrackingCache.get(tabId);
  if (cached && cached.url === url) {
    updateIcon(tabId, cached.isTracked);
    return;
  }

  // Check tracking status via API
  const result = await checkTracking(url);

  if (result && result.success) {
    const isTracked = result.data.is_tracked;

    // Cache the result
    tabTrackingCache.set(tabId, { url, isTracked });

    // Update icon
    updateIcon(tabId, isTracked);
  } else {
    // Error or not logged in - show inactive icon
    updateIcon(tabId, false);
    tabTrackingCache.delete(tabId);
  }
}

/**
 * Handle tab activation (user switches tabs)
 */
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url) {
      checkAndUpdateIcon(activeInfo.tabId, tab.url);
    }
  } catch (error) {
    console.error('[PriceTracker] Error handling tab activation:', error);
  }
});

/**
 * Handle tab updates (URL changes, page loads)
 */
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only check when page finishes loading
  if (changeInfo.status === 'complete' && tab.url) {
    checkAndUpdateIcon(tabId, tab.url);
  }
});

/**
 * Handle tab removal (cleanup cache)
 */
chrome.tabs.onRemoved.addListener((tabId) => {
  tabTrackingCache.delete(tabId);
});

/**
 * Message handler for popup communication
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'checkTracking') {
    checkTracking(message.url).then(sendResponse);
    return true; // Async response
  }

  if (message.action === 'trackProduct') {
    trackProduct(message.url, message.priority).then((result) => {
      if (result && result.success) {
        // Update icon immediately
        chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
          if (tabs[0]) {
            updateIcon(tabs[0].id, true);
            tabTrackingCache.set(tabs[0].id, { url: message.url, isTracked: true });
          }
        });
      }
      sendResponse(result);
    });
    return true; // Async response
  }

  if (message.action === 'untrackProduct') {
    untrackProduct(message.url).then((result) => {
      if (result && result.success) {
        // Update icon immediately
        chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
          if (tabs[0]) {
            updateIcon(tabs[0].id, false);
            tabTrackingCache.set(tabs[0].id, { url: message.url, isTracked: false });
          }
        });
      }
      sendResponse(result);
    });
    return true; // Async response
  }

  if (message.action === 'getSettings') {
    chrome.storage.sync.get({ defaultPriority: 2 }).then(sendResponse);
    return true; // Async response
  }
});

console.log('[PriceTracker] Background service worker loaded');
