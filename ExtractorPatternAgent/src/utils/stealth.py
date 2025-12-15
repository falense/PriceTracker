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

    # HTTP/2 can cause issues with some sites (e.g., komplett.no)
    '--disable-http2',

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
