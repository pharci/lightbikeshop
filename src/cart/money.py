from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from collections import defaultdict
from products.models import Variant
from uuid import UUID

D = Decimal
def as_kop(rub: Decimal) -> int: return int((rub*100).quantize(D("1"), rounding=ROUND_HALF_UP))

def iter_cart_variants(cart):
    if hasattr(cart, "items"):  # БД-корзина
        for ci in cart.items.select_related("variant"):
            q = int(ci.quantity or 0)
            if q > 0: yield ci.variant, q
        return

    data = getattr(cart, "cart", None)
    if not isinstance(data, dict): return

    ids = []
    for k in data.keys():
        try: ids.append(UUID(str(k)))
        except: pass
    if not ids: return

    variants = {v.id: v for v in Variant.objects.filter(id__in=ids)}
    for k, qty in data.items():
        try: u = UUID(str(k))
        except: continue
        v = variants.get(u)
        if v and int(qty or 0) > 0:
            yield v, int(qty)

def allocate_lines(variants, subtotal: Decimal, total: Decimal):
    """variants=[(Variant, qty),...] → [{variant, quantity, price, amount_kop}], сумма == total, все Amount>0"""
    ratio = (total/subtotal) if subtotal>0 else D("1")
    units = [(v, D(v.price)*ratio*100) for v,q in variants for _ in range(int(q or 0)) if v and q>0]
    if not units: return []

    # 1) округление вниз
    floors = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for _,x in units]

    # 2) требуем минимум 1 коп/юнит
    need_raise = sum(1 - f for f in floors if f < 1)
    for i, f in enumerate(floors):
        if f < 1: floors[i] = 1

    # 3) баланс к total
    target = as_kop(total)
    cur = sum(floors)

    # сначала учтём принудительные повышения (если cur>target — надо снять копейки с дорогих юнитов)
    idx = sorted(range(len(units)), key=lambda i: units[i][1] - floors[i], reverse=True)

    def dec_one():
        for j in idx:
            if floors[j] > 1:  # не уходим в 0
                floors[j] -= 1
                return True
        return False

    def inc_one():
        # добавляем к наибольшим дробям
        j = idx.pop(0); floors[j] += 1; idx.append(j)

    # если из-за min=1 перелетели — снимем разницу
    while cur > target:
        if not dec_one(): break
        cur -= 1

    # если всё ещё меньше цели — добиваем вверх
    while cur < target:
        inc_one(); cur += 1

    # 4) группировка по variant
    by = defaultdict(lambda: {"v": None, "q": 0, "sum": 0})
    for (v,_), kop in zip(units, floors):
        g = by[v.id]; g["v"]=v; g["q"]+=1; g["sum"]+=kop

    lines=[]
    for g in by.values():
        qty=g["q"]; amt=g["sum"]
        price_rub = (D(amt)/qty/D(100)).quantize(D("0.01"))
        lines.append({"variant": g["v"], "quantity": qty, "price": price_rub, "amount_kop": amt})

    # Контроли
    check_total = sum(l["amount_kop"] for l in lines)
    if check_total != as_kop(total) or any(l["amount_kop"] <= 0 for l in lines):
        return None  # сигнал ошибки
    
    return lines