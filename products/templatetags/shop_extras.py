# app_name/templatetags/shop_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    try:
        return d.get(key, '')
    except Exception:
        return ''

@register.filter
def split(value, sep=','):
    s = (value or '')
    return [p for p in s.split(sep) if p]

@register.filter
def csv_contains(csv_string, needle):
    if csv_string is None:
        return False
    items = [p for p in str(csv_string).split(',') if p]
    return str(needle) in items
