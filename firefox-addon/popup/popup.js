/**
 * PriceTracker Popup UI Logic
 *
 * Manages popup state and user interactions
 */

// State management
let currentUrl = null;
let currentState = null;

// DOM elements
const states = {
  loading: document.getElementById('loading-state'),
  login: document.getElementById('login-state'),
  notTracked: document.getElementById('not-tracked-state'),
  tracked: document.getElementById('tracked-state'),
  error: document.getElementById('error-state')
};

const confirmDialog = document.getElementById('confirm-dialog');

/**
 * Show a specific state and hide others
 * @param {string} stateName - Name of the state to show
 */
function showState(stateName) {
  Object.values(states).forEach(el => el.classList.add('hidden'));
  if (states[stateName]) {
    states[stateName].classList.remove('hidden');
    currentState = stateName;
  }
}

/**
 * Show error state with message
 * @param {string} message - Error message to display
 */
function showError(message) {
  document.getElementById('error-message').textContent = message;
  showState('error');
}

/**
 * Initialize popup - check tracking status
 */
async function init() {
  try {
    // Get current tab URL
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];

    if (!tab || !tab.url) {
      showError('Cannot access current page.');
      return;
    }

    currentUrl = tab.url;

    // Skip internal/invalid URLs
    if (!currentUrl.startsWith('http://') && !currentUrl.startsWith('https://')) {
      showError('This extension only works on web pages (http:// or https://).');
      return;
    }

    // Check tracking status via background script
    const response = await browser.runtime.sendMessage({
      action: 'checkTracking',
      url: currentUrl
    });

    if (!response) {
      showError('Failed to connect to PriceTracker. Please check your connection.');
      return;
    }

    if (response.error === 'not_logged_in') {
      showState('login');
      return;
    }

    if (!response.success) {
      showError('Failed to check tracking status. Please try again.');
      return;
    }

    // Check if product is tracked
    if (response.data.is_tracked) {
      showTrackedState(response.data);
    } else {
      showState('notTracked');
    }

  } catch (error) {
    console.error('[PriceTracker] Init error:', error);
    showError('An unexpected error occurred.');
  }
}

/**
 * Show tracked state with product details
 * @param {Object} data - Product data from API
 */
function showTrackedState(data) {
  // Update product name
  document.getElementById('product-name').textContent = data.product_name || 'Unknown Product';

  // Update current price
  const priceEl = document.getElementById('current-price');
  if (data.current_price !== null && data.current_price !== undefined) {
    priceEl.textContent = `${data.currency} ${data.current_price.toFixed(2)}`;
  } else {
    priceEl.textContent = 'Price pending...';
  }

  // Update priority
  const priorityMap = { 1: 'Low (Daily)', 2: 'Normal (Hourly)', 3: 'High (15 min)' };
  document.getElementById('priority').textContent = priorityMap[data.priority] || 'Normal';

  // Update availability
  const availabilityEl = document.getElementById('availability');
  if (data.available !== undefined) {
    availabilityEl.textContent = data.available ? 'In Stock' : 'Out of Stock';
    availabilityEl.className = data.available ? 'value status-available' : 'value status-unavailable';
  } else {
    availabilityEl.textContent = 'Unknown';
    availabilityEl.className = 'value';
  }

  showState('tracked');
}

/**
 * Add product to tracking
 */
async function trackProduct() {
  try {
    showState('loading');

    // Get default priority from settings
    const settings = await browser.runtime.sendMessage({ action: 'getSettings' });
    const priority = settings.defaultPriority || 2;

    // Track product via background script
    const response = await browser.runtime.sendMessage({
      action: 'trackProduct',
      url: currentUrl,
      priority: priority
    });

    if (!response || !response.success) {
      const errorMsg = response?.error || 'Failed to add product to tracking.';
      showError(errorMsg);
      return;
    }

    // Refresh to show tracked state
    init();

  } catch (error) {
    console.error('[PriceTracker] Track error:', error);
    showError('An error occurred while adding product.');
  }
}

/**
 * Show confirmation dialog for removal
 */
function showRemoveConfirmation() {
  confirmDialog.classList.remove('hidden');
}

/**
 * Hide confirmation dialog
 */
function hideRemoveConfirmation() {
  confirmDialog.classList.add('hidden');
}

/**
 * Remove product from tracking (after confirmation)
 */
async function untrackProduct() {
  try {
    hideRemoveConfirmation();
    showState('loading');

    // Untrack product via background script
    const response = await browser.runtime.sendMessage({
      action: 'untrackProduct',
      url: currentUrl
    });

    if (!response || !response.success) {
      const errorMsg = response?.error || 'Failed to remove product from tracking.';
      showError(errorMsg);
      return;
    }

    // Refresh to show not-tracked state
    init();

  } catch (error) {
    console.error('[PriceTracker] Untrack error:', error);
    showError('An error occurred while removing product.');
  }
}

/**
 * Open PriceTracker WebUI in new tab
 */
function openWebUI() {
  browser.tabs.create({ url: 'http://localhost:8000' });
  window.close();
}

/**
 * Open current product in WebUI
 */
function viewInWebUI() {
  browser.tabs.create({ url: 'http://localhost:8000/products/' });
  window.close();
}

// Event Listeners
document.getElementById('open-webui-btn').addEventListener('click', openWebUI);
document.getElementById('track-btn').addEventListener('click', trackProduct);
document.getElementById('remove-btn').addEventListener('click', showRemoveConfirmation);
document.getElementById('confirm-remove-btn').addEventListener('click', untrackProduct);
document.getElementById('cancel-remove-btn').addEventListener('click', hideRemoveConfirmation);
document.getElementById('view-webui-btn').addEventListener('click', viewInWebUI);
document.getElementById('retry-btn').addEventListener('click', init);

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
