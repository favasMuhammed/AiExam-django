# teacher/templatetags/exam_tags.py
from django import template

register = template.Library()

@register.filter
def intersection(queryset1, queryset2):
    return queryset1.filter(id__in=queryset2)

@register.filter
def get_ids(queryset):
    """Extracts a list of IDs from a queryset."""
    return [str(obj.id) for obj in queryset] if queryset else []

@register.filter
def get_item(dictionary, key):
    """Retrieve a value from a dictionary by key."""
    return dictionary.get(key, '') if dictionary else ''