from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """Split a string by a delimiter and return a list."""
    if value:
        return [item.strip() for item in value.split(delimiter)]
    return []


from django import template

register = template.Library()

@register.filter
def intersection(queryset1, queryset2):
    return queryset1.filter(id__in=queryset2)