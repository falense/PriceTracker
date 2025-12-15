"""
Stealth utilities for avoiding bot detection in headless browsers.

This module provides comprehensive anti-detection measures for Playwright
to make headless browsers appear like regular browsers.
"""

# Comprehensive stealth script that overrides bot detection properties
STEALTH_SCRIPT = """
// Remove webdriver property
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Add chrome object
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Override plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {
            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin},
            description: "Portable Document Format",
            filename: "internal-pdf-viewer",
            length: 1,
            name: "Chrome PDF Plugin"
        },
        {
            0: {type: "application/pdf", suffixes: "pdf", description: "", enabledPlugin: Plugin},
            description: "",
            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
            length: 1,
            name: "Chrome PDF Viewer"
        },
        {
            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable", enabledPlugin: Plugin},
            1: {type: "application/x-pnacl", suffixes: "", description: "Portable Native Client Executable", enabledPlugin: Plugin},
            description: "",
            filename: "internal-nacl-plugin",
            length: 2,
            name: "Native Client"
        }
    ]
});

// Override languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'nb-NO', 'nb']
});

// Override permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Add connection property
Object.defineProperty(navigator, 'connection', {
    get: () => ({
        effectiveType: '4g',
        rtt: 100,
        downlink: 10,
        saveData: false
    })
});

// Override platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32'
});

// Override vendor
Object.defineProperty(navigator, 'vendor', {
    get: () => 'Google Inc.'
});

// Override hardwareConcurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// Override deviceMemory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// Override maxTouchPoints
Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0
});

// Add battery API
navigator.getBattery = () => Promise.resolve({
    charging: true,
    chargingTime: 0,
    dischargingTime: Infinity,
    level: 1.0,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true
});

// Override screen properties to appear more realistic
Object.defineProperty(screen, 'availWidth', {get: () => 1920});
Object.defineProperty(screen, 'availHeight', {get: () => 1040});
Object.defineProperty(screen, 'width', {get: () => 1920});
Object.defineProperty(screen, 'height', {get: () => 1080});
Object.defineProperty(screen, 'colorDepth', {get: () => 24});
Object.defineProperty(screen, 'pixelDepth', {get: () => 24});

// Override AudioContext
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.apply(this, [parameter]);
};

// Add MediaDevices
navigator.mediaDevices = {
    enumerateDevices: () => Promise.resolve([
        {
            deviceId: "default",
            kind: "audioinput",
            label: "Default - Microphone",
            groupId: "default"
        },
        {
            deviceId: "default",
            kind: "audiooutput",
            label: "Default - Speaker",
            groupId: "default"
        }
    ]),
    getUserMedia: () => Promise.reject(new Error('Permission denied'))
};

// Mock Notification API
window.Notification = class Notification extends EventTarget {
    constructor(title, options) {
        super();
        this.title = title;
        this.options = options;
    }
    static get permission() { return 'default'; }
    static requestPermission() { return Promise.resolve('default'); }
};

// Make toString() return native code for overridden functions
const makeNativeString = (fn) => {
    const handler = {
        apply: function(target, ctx, args) {
            return target.apply(ctx, args);
        },
        get: function(target, prop) {
            if (prop === 'toString') {
                return function() {
                    return 'function ' + target.name + '() { [native code] }';
                };
            }
            return target[prop];
        }
    };
    return new Proxy(fn, handler);
};

// Apply native code appearance
navigator.getBattery = makeNativeString(navigator.getBattery);
"""

# Browser launch arguments for maximum stealth
STEALTH_ARGS = [
    # Essential for Docker
    '--no-sandbox',
    '--disable-setuid-sandbox',

    # Disable automation flags
    '--disable-blink-features=AutomationControlled',

    # Memory and performance
    '--disable-dev-shm-usage',

    # Additional stealth
    '--disable-web-security',
    '--disable-features=IsolateOrigins,site-per-process',
    '--disable-features=VizDisplayCompositor',

    # Avoid detection
    '--disable-features=site-per-process',
    '--disable-infobars',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-renderer-backgrounding',

    # Language and locale
    '--lang=en-US,en',
]

# Headers that mimic a real browser
STEALTH_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9,nb-NO;q=0.8,nb;q=0.7',
    'Cache-Control': 'max-age=0',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}

# User agent that appears as a real Chrome browser
STEALTH_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


async def apply_stealth(page):
    """
    Apply stealth script to a Playwright page.

    Args:
        page: Playwright page object
    """
    await page.add_init_script(STEALTH_SCRIPT)


def get_stealth_context_options():
    """
    Get browser context options for maximum stealth.

    Returns:
        Dictionary of context options
    """
    return {
        'user_agent': STEALTH_USER_AGENT,
        'viewport': {'width': 1920, 'height': 1080},
        'screen': {'width': 1920, 'height': 1080},
        'locale': 'en-US',
        'timezone_id': 'America/New_York',
        'geolocation': {'longitude': -73.935242, 'latitude': 40.730610},  # New York
        'permissions': ['geolocation'],
        'color_scheme': 'light',
        'extra_http_headers': STEALTH_HEADERS,
        'java_script_enabled': True,
        'has_touch': False,
        'is_mobile': False,
        'device_scale_factor': 1,
    }


# Enhanced stealth utilities for difficult sites (e.g., Amazon)
import random
import asyncio


async def simulate_human_behavior(page, domain: str = ""):
    """
    Simulate human-like behavior on a page to avoid detection.

    Args:
        page: Playwright page object
        domain: Domain being accessed (for domain-specific behavior)
    """
    # Random mouse movements
    await random_mouse_movements(page)

    # Random scrolling
    await random_scroll(page)

    # Wait for a random "think time"
    think_time = random.uniform(1.5, 3.5)
    if "amazon" in domain.lower():
        # Amazon needs longer delays
        think_time = random.uniform(3.0, 6.0)

    await asyncio.sleep(think_time)


async def random_mouse_movements(page, num_moves: int = None):
    """
    Simulate random mouse movements across the page.

    Args:
        page: Playwright page object
        num_moves: Number of mouse movements (random if None)
    """
    if num_moves is None:
        num_moves = random.randint(3, 7)

    viewport_size = page.viewport_size
    max_x = viewport_size['width']
    max_y = viewport_size['height']

    for _ in range(num_moves):
        x = random.randint(100, max_x - 100)
        y = random.randint(100, max_y - 100)

        # Move mouse with slight delay
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))


async def random_scroll(page):
    """
    Simulate human-like scrolling behavior.

    Args:
        page: Playwright page object
    """
    # Get page height
    page_height = await page.evaluate("() => document.body.scrollHeight")
    viewport_height = page.viewport_size['height']

    if page_height <= viewport_height:
        # Page is too short to scroll
        return

    # Scroll down in random increments
    current_position = 0
    num_scrolls = random.randint(2, 4)

    for _ in range(num_scrolls):
        scroll_amount = random.randint(200, 500)
        current_position += scroll_amount

        # Don't scroll past page height
        if current_position > page_height - viewport_height:
            current_position = page_height - viewport_height

        await page.evaluate(f"window.scrollTo(0, {current_position})")
        await asyncio.sleep(random.uniform(0.3, 0.8))

    # Scroll back to top
    await asyncio.sleep(random.uniform(0.5, 1.0))
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(random.uniform(0.3, 0.6))


async def wait_for_stable_load(page, timeout: int = 30000):
    """
    Wait for page to be fully loaded with all dynamic content.

    Args:
        page: Playwright page object
        timeout: Maximum wait time in milliseconds
    """
    try:
        # Wait for network to be idle
        await page.wait_for_load_state('networkidle', timeout=timeout)
    except Exception:
        # If networkidle times out, just ensure DOM is loaded
        await page.wait_for_load_state('domcontentloaded', timeout=timeout)

    # Extra wait for lazy-loaded images
    await asyncio.sleep(random.uniform(1.0, 2.0))


def get_enhanced_context_options(domain: str = ""):
    """
    Get enhanced browser context options for difficult sites.

    Args:
        domain: Domain being accessed (for domain-specific options)

    Returns:
        Dictionary of context options
    """
    options = get_stealth_context_options()

    # For Amazon and other strict sites, add more realistic options
    if "amazon" in domain.lower():
        options.update({
            'locale': 'en-US,en',
            'timezone_id': 'America/Los_Angeles',  # Vary timezone
            'geolocation': {'longitude': -122.419418, 'latitude': 37.774929},  # San Francisco
        })

    return options
