"""
Context processors for Følgpris templates.
Make site constants and common data available in all templates.
"""
from app import constants


def site_constants(request):
    """Make site constants available in all templates."""
    return {
        'SITE_NAME': constants.SITE_NAME,
        'SITE_TAGLINE': constants.SITE_TAGLINE,
        'NAV': {
            'dashboard': constants.NAV_DASHBOARD,
            'products': constants.NAV_PRODUCTS,
            'notifications': constants.NAV_NOTIFICATIONS,
            'settings': constants.NAV_SETTINGS,
            'admin': constants.NAV_ADMIN,
            'pricing': constants.NAV_PRICING,
            'about': constants.NAV_ABOUT,
        },
        'ACTIONS': {
            'track': constants.ACTION_TRACK,
            'unfollow': constants.ACTION_UNFOLLOW,
            'search': constants.ACTION_SEARCH,
            'login': constants.ACTION_LOGIN,
            'logout': constants.ACTION_LOGOUT,
            'register': constants.ACTION_REGISTER,
            'update': constants.ACTION_UPDATE,
            'delete': constants.ACTION_DELETE,
            'refresh': constants.ACTION_REFRESH,
            'save': constants.ACTION_SAVE,
            'cancel': constants.ACTION_CANCEL,
            'send': constants.ACTION_SEND,
            'view_details': constants.ACTION_VIEW_DETAILS,
            'view_all': constants.ACTION_VIEW_ALL,
            'add_product': constants.ACTION_ADD_PRODUCT,
        },
    }
