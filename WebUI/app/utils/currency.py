"""
Currency utilities for mapping domains to currencies and formatting prices.
"""
from typing import Dict, Tuple


# Domain TLD to currency mapping
TLD_CURRENCY_MAP = {
    'no': ('NOK', 'kr'),     # Norwegian Krone
    'se': ('SEK', 'kr'),     # Swedish Krona
    'dk': ('DKK', 'kr'),     # Danish Krone
    'uk': ('GBP', '£'),      # British Pound
    'de': ('EUR', '€'),      # Euro
    'fr': ('EUR', '€'),      # Euro
    'es': ('EUR', '€'),      # Euro
    'it': ('EUR', '€'),      # Euro
    'nl': ('EUR', '€'),      # Euro
    'com': ('USD', '$'),     # US Dollar
    'ca': ('CAD', 'CA$'),    # Canadian Dollar
    'au': ('AUD', 'A$'),     # Australian Dollar
    'nz': ('NZD', 'NZ$'),    # New Zealand Dollar
    'jp': ('JPY', '¥'),      # Japanese Yen
    'cn': ('CNY', '¥'),      # Chinese Yuan
    'in': ('INR', '₹'),      # Indian Rupee
    'br': ('BRL', 'R$'),     # Brazilian Real
    'mx': ('MXN', 'MX$'),    # Mexican Peso
}


def get_currency_from_domain(domain: str) -> Tuple[str, str]:
    """
    Get currency code and symbol from domain.

    Args:
        domain: Domain name (e.g., 'amazon.no', 'ebay.com')

    Returns:
        Tuple of (currency_code, currency_symbol)
        Defaults to ('USD', '$') if domain TLD is not recognized
    """
    if not domain:
        return ('USD', '$')

    # Extract TLD (last part after final dot)
    parts = domain.lower().split('.')
    if len(parts) < 2:
        return ('USD', '$')

    tld = parts[-1]
    return TLD_CURRENCY_MAP.get(tld, ('USD', '$'))


def format_price(price: float, domain: str = None, currency_code: str = None) -> str:
    """
    Format price with appropriate currency symbol.

    Args:
        price: Price value
        domain: Domain name (optional, used to determine currency)
        currency_code: Currency code (optional, overrides domain-based detection)

    Returns:
        Formatted price string (e.g., '$99.99', 'kr 499')
    """
    if price is None:
        return 'N/A'

    # Determine currency
    if currency_code:
        # Look up symbol from currency code
        symbol = None
        for tld, (code, sym) in TLD_CURRENCY_MAP.items():
            if code == currency_code:
                symbol = sym
                break
        if not symbol:
            symbol = currency_code + ' '
    elif domain:
        currency_code, symbol = get_currency_from_domain(domain)
    else:
        currency_code, symbol = ('USD', '$')

    # Format based on currency convention
    if currency_code in ['NOK', 'SEK', 'DKK']:
        # Scandinavian currencies: symbol after amount with space
        return f"{price:.2f} {symbol}"
    elif currency_code == 'EUR':
        # Euro: symbol before with space (common in many EU countries)
        return f"{symbol} {price:.2f}"
    else:
        # Default: symbol before without space (USD, GBP, etc.)
        return f"{symbol}{price:.2f}"
