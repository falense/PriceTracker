"""
Django template filters for currency formatting.
"""
from django import template
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
