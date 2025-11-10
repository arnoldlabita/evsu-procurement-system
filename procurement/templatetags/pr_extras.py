from django import template

register = template.Library()

@register.filter
def chunk_items(items, chunk_size):
    try:
        chunk_size = int(chunk_size)
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    except Exception:
        return []

@register.filter
def sum_attr(items, attr):
    try:
        return sum(getattr(item, attr, 0) for item in items)
    except Exception:
        return 0

@register.filter
def mul(value, arg):
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

