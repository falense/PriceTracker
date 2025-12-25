/**
 * PriceTracker Options/Settings Page Logic (Chrome Version)
 */

// DOM elements
const prioritySelect = document.getElementById('priority-select');
const saveBtn = document.getElementById('save-btn');
const resetBtn = document.getElementById('reset-btn');
const statusMessage = document.getElementById('status-message');
const statusText = document.getElementById('status-text');

/**
 * Load settings from storage
 */
async function loadSettings() {
  try {
    const settings = await chrome.storage.sync.get({
      defaultPriority: 2  // Default to normal priority
    });

    prioritySelect.value = settings.defaultPriority;
  } catch (error) {
    console.error('[PriceTracker] Error loading settings:', error);
    showStatus('Failed to load settings', 'error');
  }
}

/**
 * Save settings to storage
 */
async function saveSettings() {
  try {
    const priority = parseInt(prioritySelect.value, 10);

    // Validate priority
    if (![1, 2, 3].includes(priority)) {
      showStatus('Invalid priority value', 'error');
      return;
    }

    // Save to storage
    await chrome.storage.sync.set({
      defaultPriority: priority
    });

    showStatus('Settings saved successfully!', 'success');
  } catch (error) {
    console.error('[PriceTracker] Error saving settings:', error);
    showStatus('Failed to save settings', 'error');
  }
}

/**
 * Reset settings to defaults
 */
async function resetSettings() {
  try {
    // Reset to default priority (normal = 2)
    await chrome.storage.sync.set({
      defaultPriority: 2
    });

    // Update UI
    prioritySelect.value = 2;

    showStatus('Settings reset to defaults', 'success');
  } catch (error) {
    console.error('[PriceTracker] Error resetting settings:', error);
    showStatus('Failed to reset settings', 'error');
  }
}

/**
 * Show status message
 * @param {string} message - Message to display
 * @param {string} type - Message type ('success' or 'error')
 */
function showStatus(message, type = 'success') {
  statusText.textContent = message;
  statusMessage.className = `status-message ${type}`;
  statusMessage.classList.remove('hidden');

  // Hide after 3 seconds
  setTimeout(() => {
    statusMessage.classList.add('hidden');
  }, 3000);
}

// Event Listeners
saveBtn.addEventListener('click', saveSettings);
resetBtn.addEventListener('click', resetSettings);

// Load settings when page loads
document.addEventListener('DOMContentLoaded', loadSettings);
