# dashboard/admin_index.py
import datetime as dt
from django.contrib.admin.sites import site
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.core.cache import cache
from cart.models import Order

TZ = timezone.get_current_timezone()

def _dt(d, end=False):
    t = dt.time.max if end else dt.time.min
    return timezone.make_aware(dt.datetime.combine(d, t), TZ)

def _series(*, period: str = "7d", shift: int = 0, start_date: dt.date | None = None, end_date: dt.date | None = None):
    custom = start_date is not None and end_date is not None

    if custom:
        start = _dt(start_date, end=False)
        end   = _dt(end_date,   end=True)
        eff_period = "custom"
        eff_shift = 0
    elif period == "all":
        first_dt = Order.objects.order_by("date_ordered").values_list("date_ordered", flat=True).first()
        if first_dt:
            first_day = timezone.localtime(first_dt, TZ).date()
        else:
            first_day = timezone.localdate()
        start = _dt(first_day, end=False)
        end   = _dt(timezone.localdate(), end=True)
        eff_period = "all"
        eff_shift = 0
    else:
        n = 7 if period == "7d" else 30
        today = timezone.localdate()
        end_day = today - dt.timedelta(days=n * shift)
        start_day = end_day - dt.timedelta(days=n - 1)
        start = _dt(start_day, end=False)
        end   = _dt(end_day,   end=True)
        eff_period = period
        eff_shift = shift

    # cache key
    if custom:
        key = f"adm:orders:custom:{start.date().isoformat()}:{end.date().isoformat()}"
    else:
        key = f"adm:orders:{eff_period}:{eff_shift}:{int(_dt(start.date()).timestamp())}:{int(_dt(end.date(),True).timestamp())}"

    cached = cache.get(key)
    if cached:
        return cached

    qs = (
        Order.objects
        .filter(date_ordered__gte=start, date_ordered__lte=end)
        .annotate(d=TruncDate("date_ordered"))
        .values("d").order_by("d")
        .annotate(c=Count("id"))
    )
    by_day = {r["d"]: int(r["c"]) for r in qs}

    s_day = start.date()
    e_day = end.date()
    labels, counts = [], []
    cur = s_day
    while cur <= e_day:
        labels.append(cur.isoformat())
        counts.append(by_day.get(cur, 0))
        cur += dt.timedelta(days=1)

    data = {
        "labels": labels,
        "counts": counts,
        "total": int(sum(counts)),
        "start": start,
        "end": end,
        "period": eff_period,
        "shift": eff_shift,
    }
    cache.set(key, data, 300)
    return data

@staff_member_required
def admin_index(request):
    qs = request.GET
    today = timezone.localdate()

    start_s = qs.get("start")
    end_s = qs.get("end")
    start_date = end_date = None
    if start_s and end_s:
        try:
            sd = dt.datetime.strptime(start_s, "%Y-%m-%d").date()
            ed = dt.datetime.strptime(end_s, "%Y-%m-%d").date()
            if ed > today:
                ed = today
            if sd > ed:
                sd = ed
            start_date, end_date = sd, ed
        except ValueError:
            start_date = end_date = None

    if start_date and end_date:
        orders = _series(start_date=start_date, end_date=end_date)
    else:
        period = qs.get("period", "7d")
        try:
            shift = int(qs.get("shift", "0"))
        except ValueError:
            shift = 0
        orders = _series(period=period, shift=shift)

    ctx = site.each_context(request)
    ctx["title"] = "Администрирование"
    ctx["app_list"] = list(site.get_app_list(request))
    ctx.update({
        "ord_labels": orders["labels"],
        "ord_counts": orders["counts"],
        "ord_total": orders["total"],
        "ord_period": orders["period"],
        "ord_shift": orders["shift"],
        "ord_start": timezone.localtime(orders["start"]),
        "ord_end": timezone.localtime(orders["end"]),
    })
    return TemplateResponse(request, "admin/index.html", ctx)