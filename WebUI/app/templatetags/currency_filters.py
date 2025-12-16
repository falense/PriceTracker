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
