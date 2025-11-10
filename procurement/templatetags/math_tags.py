from django import template
register = template.Library()

@register.filter
def subtotal(items, count):
    """Return subtotal for first 'count' items."""
    total = 0
    for item in items[:count]:
        # If total_cost is a method, call it
        value = item.total_cost() if callable(item.total_cost) else item.total_cost
        total += value or 0
    return total
