"""
Django template filters for currency formatting and JSON serialization.
"""
import json
from django import template
from django.utils.safestring import mark_safe
from app.utils.currency import format_price, get_currency_from_domain

register = template.Library()


@register.filter(name='format_currency')
def format_currency(price, domain):
    """
    Format price with appropriate currency symbol based on domain.

    Usage in template:
        {{ product.current_price|format_currency:product.domain }}
    """
    return format_price(price, domain=domain)


@register.filter(name='currency_symbol')
def currency_symbol(domain):
    """
    Get currency symbol for a domain.

    Usage in template:
        {{ product.domain|currency_symbol }}
    """
    _, symbol = get_currency_from_domain(domain)
    return symbol


@register.filter(name='to_json')
def to_json(value):
    """
    Convert a Python object to JSON string.

    Usage in template:
        {{ log.context|to_json }}
    """
    if value is None:
        return 'null'
    try:
        return mark_safe(json.dumps(value, default=str, ensure_ascii=False))
    except (TypeError, ValueError):
        return '{}'


@register.filter(name='truncate_path')
def truncate_path(url, max_length=50):
    """
    Truncate URL to show only path, with intelligent truncation.

    Usage in template:
        {{ log.context.url|truncate_path }}
        {{ log.context.url|truncate_path:40 }}
    """
    if not url:
        return ''
    try:
        from urllib.parse import urlparse
        parsed = urlparse(str(url))
        path = parsed.path or url

        if len(path) > max_length:
            # Keep start and end, truncate middle
            keep_each = (max_length - 3) // 2
            return path[:keep_each] + '...' + path[-keep_each:]
        return path
    except Exception:
        # Fallback: simple string truncation
        url_str = str(url)
        if len(url_str) > max_length:
            return url_str[:max_length-3] + '...'
        return url_str


@register.filter(name='context_value')
def context_value(context_dict, key):
    """
    Safely get a value from context dict.

    Usage in template:
        {{ log.context|context_value:"url" }}
    """
    if not context_dict or not isinstance(context_dict, dict):
        return None
    return context_dict.get(key)
