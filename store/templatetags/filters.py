from django.template import Library
from store.models import WishlistItem
register = Library()

@register.filter()
def add_thousand_separators(value):
    try:
        return "{:,}".format(int(value)).replace(',', ' ')
    except (ValueError, TypeError):
        return value
    
@register.filter()
def discount_percentage(old_price, new_price):
    try:
        return 100 - (100 * new_price / old_price)
    except ZeroDivisionError:
        return 0
    
@register.filter()
def get_attr(dictionary, attr_slug):
    key = f'attr_{attr_slug}' 
    lists = dictionary.lists()
    dictionary = dict(lists)
    return dictionary.get(key, [])

@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    request = context['request']
    updated = request.GET.copy()
    
    for key, value in kwargs.items():
        if value is None:
            updated.pop(key, None)
        else:
            updated[key] = value

    return updated.urlencode()

@register.filter(name='is_in_wishlist')
def is_in_wishlist(variant, user):
    if user.is_authenticated:
        return WishlistItem.objects.filter(
            wishlist__user=user,
            product_variant=variant
        ).exists()
    return False

@register.filter(name='pluralize_goods')
def pluralize_goods(value):
    value = int(value)  # Убедимся, что value это число
    if 10 <= value % 100 <= 20:
        return f'{value} товаров'
    elif value % 10 == 1:
        return f'{value} товар'
    elif 2 <= value % 10 <= 4:
        return f'{value} товара'
    else:
        return f'{value} товаров'
    
@register.filter
def order_by_checked(values, selected_attributes):
    all_selected_values = []
    
    for key, values_list in selected_attributes.lists():
        all_selected_values.extend(values_list)
    checked_values = [v for v in values if v.value_en in all_selected_values]
    unchecked_values = [v for v in values if v.value_en not in all_selected_values]
    return checked_values + unchecked_values

@register.filter
def get_variant_quantity_in_cart(variant, cart):
    if cart and variant:
        try:
            cart_item = cart.items.get(variant=variant)
            return cart_item.quantity
        except cart.items.model.DoesNotExist:
            return 0
    return 0