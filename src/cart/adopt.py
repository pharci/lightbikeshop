# cart/adopt.py
from __future__ import annotations
from django.db import transaction
from .models import Cart, CartItem, SessionCart
from cart.views.cart import get_cart  # твоя функция get_cart

@transaction.atomic
def adopt_session_cart(request, user) -> None:
    sc_like = get_cart(request)
    if not isinstance(sc_like, SessionCart):
        return

    sc: SessionCart = sc_like
    items = sc.get_items()
    promo = sc.get_promo_obj()

    if not items and not promo:
        return

    cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
    existing = {ci.variant_id: ci for ci in cart.items.all()}

    # суммируем количества по variant_id
    agg: dict[int, int] = {}
    for it in items:
        vid = int(it["variant"]["id"])
        qty = int(it["quantity"])
        if qty > 0:
            agg[vid] = agg.get(vid, 0) + qty

    for vid, qty in agg.items():
        ci = existing.get(vid)
        if ci:
            ci.quantity = max(1, ci.quantity + qty)
            ci.save(update_fields=["quantity"])
        else:
            CartItem.objects.create(cart=cart, variant_id=vid, quantity=qty)

    if promo:
        cart.apply_promo(promo, user=user)

    sc.clear()