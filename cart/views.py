from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from store.models import ProductVariant
from django.core.mail import send_mail
from accounts.utils import send_telegram_message
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Cart


def cart(request):

    return render(request, "cart/cart.html")

@require_POST
def add_to_cart(request):
    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    try:
        variant = ProductVariant.objects.get(id=variant_id)
    except ProductVariant.DoesNotExist:
        return JsonResponse({'error': 'Variant not found'}, status=404)
    
    cart = Cart.create_cart(request)
    cart_item = cart.add(variant, quantity)
    
    return JsonResponse({'success': True, 'quantity': cart_item.quantity})

@require_POST
def remove_from_cart(request):
    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    try:
        variant = ProductVariant.objects.get(id=variant_id)
    except ProductVariant.DoesNotExist:
        return JsonResponse({'error': 'Variant not found'}, status=404)
    
    cart = Cart.get_cart(request)
    cart_item = cart.remove(variant, quantity)

    if cart_item:
        return JsonResponse({'success': True, 'quantity': cart_item.quantity})
    else:
        return JsonResponse({'error': 'Cart item not found'}, status=404)