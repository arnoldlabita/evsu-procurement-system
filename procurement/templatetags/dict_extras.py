# procurement/templatetags/dict_extras.py
from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely gets a key from a dictionary inside Django templates.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
