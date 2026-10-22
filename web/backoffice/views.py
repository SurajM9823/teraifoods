from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from catalog.models import Product, Category, Order
from .forms import AdminLoginForm
from .selectors import get_dashboard_summary


class AdminLoginView(LoginView):
    template_name = "web/backoffice/login.html"
    authentication_form = AdminLoginForm
    next_page = reverse_lazy("backoffice:dashboard")


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("backoffice:login")


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def dashboard(request):
    context = get_dashboard_summary(user=request.user)
    context.update({
        "active_page": "overview",
        "page_title": "Overview",
    })
    return render(request, "web/backoffice/dashboard.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
def orders(request):
    return redirect("/admin/orders/")


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
def bulk_orders(request):
    return redirect("/admin/bulk-orders/")


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
def products(request):
    return redirect("products:index")


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def pos(request):
    categories = Category.objects.filter(is_active=True).order_by("name")
    products_qs = Product.objects.filter(is_active=True, is_archived=False).select_related("category").order_by("name")
    q = request.GET.get("q", "").strip()
    if q:
        products_qs = products_qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    cat_id = request.GET.get("category", "").strip()
    if cat_id:
        products_qs = products_qs.filter(category_id=cat_id)
    page = Paginator(products_qs, 25).get_page(request.GET.get("page"))
    context = {
        "active_page": "pos",
        "page_title": "Point of Sale",
        "categories": categories,
        "page": page,
    }
    return render(request, "web/backoffice/pos.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def web_analytics(request):
    traffic_sources = [
        {"source": "Direct Search & Bookmark", "percentage": 42, "visitors": "6,012"},
        {"source": "Google Organic Search", "percentage": 33, "visitors": "4,712"},
        {"source": "Social Media (Instagram/FB)", "percentage": 15, "visitors": "2,142"},
        {"source": "Wholesale Direct & Email", "percentage": 10, "visitors": "1,414"},
    ]
    top_pages = [
        {"page": "/product/himalayan-basmati-rice", "title": "Himalayan Basmati Rice", "views": "12,430", "conversions": "412"},
        {"page": "/product/cold-pressed-mustard-oil", "title": "Cold-Pressed Mustard Oil", "views": "9,850", "conversions": "320"},
        {"page": "/bulk-order", "title": "Wholesale Bulk Order", "views": "7,110", "conversions": "184"},
        {"page": "/product/pure-cow-ghee", "title": "Pure Cow Ghee", "views": "5,690", "conversions": "196"},
    ]
    context = {
        "active_page": "analytics",
        "page_title": "Web Analytics",
        "metrics": {
            "visitors": "14,280",
            "page_views": "58,920",
            "conversion_rate": "3.42%",
            "avg_order_value": "£42.80",
        },
        "traffic_sources": traffic_sources,
        "top_pages": top_pages,
    }
    return render(request, "web/backoffice/analytics.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def customers(request):
    User = get_user_model()
    users_qs = User.objects.annotate(
        orders_count=Count("order"),
        total_spent=Coalesce(
            Sum("order__total", filter=Q(order__payment_status="paid")),
            Value(Decimal("0.00"), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).order_by("-date_joined")

    q = request.GET.get("q", "").strip()
    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter == "active":
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == "inactive":
        users_qs = users_qs.filter(is_active=False)
    elif status_filter == "staff":
        users_qs = users_qs.filter(is_staff=True)

    total_count = User.objects.count()
    active_count = User.objects.filter(is_active=True).count()
    staff_count = User.objects.filter(is_staff=True).count()
    total_spent_val = Order.objects.filter(payment_status="paid").aggregate(s=Sum("total"))["s"] or Decimal("0.00")

    page = Paginator(users_qs, 25).get_page(request.GET.get("page"))
    context = {
        "active_page": "customers",
        "page_title": "Customers",
        "page": page,
        "stats": {
            "total": total_count,
            "active": active_count,
            "staff": staff_count,
            "total_spent": f"{total_spent_val:.2f}",
        },
    }
    return render(request, "web/backoffice/customers.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
def site_settings(request):
    settings_data = {
        "store_name": "Terai Food UK",
        "support_email": "support@teraifood.co.uk",
        "phone": "+44 20 7946 0199",
        "address": "Unit 4, Himalayan Trading Estate, London, E1 6AN",
        "currency": "GBP (£)",
        "timezone": "Europe/London (GMT)",
        "free_delivery_threshold": "50.00",
        "standard_delivery_fee": "4.99",
        "vat_rate": "0% (Food Staples Zero-Rated)",
        "wholesale_minimum_order": "150.00",
    }
    saved = False
    if request.method == "POST":
        saved = True
    context = {
        "active_page": "settings",
        "page_title": "Site Settings",
        "settings": settings_data,
        "saved": saved,
    }
    return render(request, "web/backoffice/settings.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def pricing_tier_groups(request):
    tier_groups = [
        {
            "name": "Retail Standard",
            "code": "RETAIL",
            "discount": "0%",
            "min_order": "£0.00",
            "payment_terms": "Immediate Checkout",
            "members_count": 1156,
            "is_default": True,
        },
        {
            "name": "Wholesale Tier 1 (Silver)",
            "code": "WHOLESALE_SILVER",
            "discount": "10% off Catalog",
            "min_order": "£150.00",
            "payment_terms": "Proforma / Net-14",
            "members_count": 52,
            "is_default": False,
        },
        {
            "name": "Wholesale Tier 2 (Gold)",
            "code": "WHOLESALE_GOLD",
            "discount": "20% off Catalog",
            "min_order": "£500.00",
            "payment_terms": "Net-30 Invoice",
            "members_count": 24,
            "is_default": False,
        },
        {
            "name": "Restaurant & Hospitality Partner",
            "code": "HOSPITALITY",
            "discount": "Custom Contract Rates",
            "min_order": "£300.00",
            "payment_terms": "Net-30 Weekly Delivery",
            "members_count": 8,
            "is_default": False,
        },
    ]
    pricing_rules = [
        {
            "product": "Himalayan Basmati Rice (5kg bags)",
            "tier": "Wholesale Tier 1 (Silver)",
            "moq": "10 units",
            "unit_price": "£10.50",
            "savings": "Save 16%",
            "status": "Active",
        },
        {
            "product": "Himalayan Basmati Rice (20kg sacks)",
            "tier": "Wholesale Tier 2 (Gold)",
            "moq": "5 sacks",
            "unit_price": "£36.00",
            "savings": "Save 25%",
            "status": "Active",
        },
        {
            "product": "Cold-Pressed Mustard Oil (Carton of 12)",
            "tier": "Wholesale Tier 1 (Silver)",
            "moq": "2 cartons",
            "unit_price": "£62.00 / ctn",
            "savings": "Save 24%",
            "status": "Active",
        },
        {
            "product": "Wild Timut Pepper Bulk Pack",
            "tier": "Restaurant Partner",
            "moq": "5 kg",
            "unit_price": "£28.00 / kg",
            "savings": "Contract",
            "status": "Active",
        },
        {
            "product": "Red Lentils & Moong Dal (25kg bags)",
            "tier": "Wholesale Tier 2 (Gold)",
            "moq": "4 bags",
            "unit_price": "£42.00 / bag",
            "savings": "Save 20%",
            "status": "Active",
        },
    ]
    context = {
        "active_page": "pricing",
        "page_title": "Pricing & Tier Group",
        "tier_groups": tier_groups,
        "pricing_rules": pricing_rules,
    }
    return render(request, "web/backoffice/pricing.html", context)
