from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

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
@require_safe
def orders(request):
    orders_list = [
        {
            "id": "TF-2041",
            "customer": "Priya Sharma",
            "email": "priya.sharma@example.co.uk",
            "type": "Retail",
            "items_summary": "Himalayan Basmati Rice 5kg, Mustard Oil 1L",
            "total": "£28.50",
            "payment_status": "Paid",
            "fulfillment_status": "Processing",
            "date": "Today, 14:22",
        },
        {
            "id": "TF-2040",
            "customer": "Himalayan Spice Bistro (Leeds)",
            "email": "procurement@himalayanspice.co.uk",
            "type": "Wholesale Tier 2",
            "items_summary": "Red Lentils 25kg, Turmeric 5kg, Cumin 5kg",
            "total": "£184.00",
            "payment_status": "Paid",
            "fulfillment_status": "Shipped",
            "date": "Today, 11:05",
        },
        {
            "id": "TF-2039",
            "customer": "Sunil Thapa",
            "email": "sunil.thapa@example.co.uk",
            "type": "Retail",
            "items_summary": "Moong Dal 2kg, Chiura 1kg, Timut Pepper 100g",
            "total": "£19.75",
            "payment_status": "Paid",
            "fulfillment_status": "Delivered",
            "date": "Yesterday, 17:40",
        },
        {
            "id": "TF-2038",
            "customer": "Kathmandu Kitchen (London)",
            "email": "chef@kathmandukitchen.co.uk",
            "type": "Wholesale Tier 1",
            "items_summary": "Himalayan Basmati 50kg, Mustard Oil 15L",
            "total": "£320.00",
            "payment_status": "Pending",
            "fulfillment_status": "Processing",
            "date": "Yesterday, 12:15",
        },
        {
            "id": "TF-2037",
            "customer": "Aarav Patel",
            "email": "aarav.patel@example.co.uk",
            "type": "Retail",
            "items_summary": "Ginger Garlic Paste, Ghee 1kg, Garam Masala",
            "total": "£24.90",
            "payment_status": "Paid",
            "fulfillment_status": "Delivered",
            "date": "16 Oct 2026",
        },
        {
            "id": "TF-2036",
            "customer": "Anita Gurung",
            "email": "anita.gurung@example.co.uk",
            "type": "Retail",
            "items_summary": "Green Cardamom 250g, Black Cardamom 200g",
            "total": "£16.20",
            "payment_status": "Refunded",
            "fulfillment_status": "Cancelled",
            "date": "15 Oct 2026",
        },
    ]
    context = {
        "active_page": "orders",
        "page_title": "Orders",
        "orders_list": orders_list,
        "summary": {
            "total_orders": 148,
            "processing": 12,
            "dispatched": 26,
            "total_revenue": "£8,420.50",
        },
    }
    return render(request, "web/backoffice/orders.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def bulk_orders(request):
    inquiries_list = [
        {
            "id": "INQ-901",
            "company": "Curry Lounge Group (Birmingham)",
            "contact_name": "Ramesh Kulkarni",
            "email": "orders@currylounge.co.uk",
            "phone": "+44 121 496 0233",
            "products": "Himalayan Basmati Rice (500 kg), Mustard Oil (120 L)",
            "est_value": "£2,140.00",
            "status": "New",
            "urgency": "High",
            "date": "Today, 14:10",
            "delivery_postcode": "B1 1BB",
        },
        {
            "id": "INQ-900",
            "company": "Himalayan Spice Emporium (London)",
            "contact_name": "Deepak Thapa",
            "email": "procurement@himalayanspice.co.uk",
            "phone": "+44 20 7946 0881",
            "products": "Wild Timut Pepper (40 kg), Black Cardamom (25 kg), Turmeric (50 kg)",
            "est_value": "£1,860.00",
            "status": "Quoted",
            "urgency": "Normal",
            "date": "Yesterday, 16:45",
            "delivery_postcode": "E1 6AN",
        },
        {
            "id": "INQ-899",
            "company": "Everest Catering Ltd (Manchester)",
            "contact_name": "Pooja Gurung",
            "email": "pooja@everestcatering.co.uk",
            "phone": "+44 161 496 0772",
            "products": "Red Lentils Masoor (1,000 kg), Moong Dal (400 kg), Chiura (200 kg)",
            "est_value": "£4,250.00",
            "status": "Under Review",
            "urgency": "Normal",
            "date": "16 Oct 2026",
            "delivery_postcode": "M1 4ET",
        },
        {
            "id": "INQ-898",
            "company": "Namaste UK Distribution (Leeds)",
            "contact_name": "Suresh Adhikari",
            "email": "warehouse@namasteuk.com",
            "phone": "+44 113 496 0411",
            "products": "Pure Cow Ghee (300 kg), Basmati Rice (2,000 kg)",
            "est_value": "£7,800.00",
            "status": "Converted",
            "urgency": "Low",
            "date": "14 Oct 2026",
            "delivery_postcode": "LS1 2AB",
        },
        {
            "id": "INQ-897",
            "company": "Kathmandu Kitchen (Reading)",
            "contact_name": "Arun Shrestha",
            "email": "chef@kathmandureading.co.uk",
            "phone": "+44 118 496 0300",
            "products": "Mustard Oil (60 L), Timut Pepper (10 kg)",
            "est_value": "£590.00",
            "status": "Quoted",
            "urgency": "Normal",
            "date": "12 Oct 2026",
            "delivery_postcode": "RG1 1DN",
        },
        {
            "id": "INQ-896",
            "company": "Green Valley Organics (Bristol)",
            "contact_name": "Sophie Jenkins",
            "email": "procure@greenvalley.co.uk",
            "phone": "+44 117 496 0199",
            "products": "Organic Red Lentils (250 kg), Yellow Split Peas (250 kg)",
            "est_value": "£1,350.00",
            "status": "Rejected",
            "urgency": "Low",
            "date": "10 Oct 2026",
            "delivery_postcode": "BS1 3XE",
        },
    ]
    context = {
        "active_page": "bulk_orders",
        "page_title": "Bulk Order Inquiries",
        "inquiries_list": inquiries_list,
        "summary": {
            "total_inquiries": 24,
            "new_requests": 5,
            "awaiting_quote": 3,
            "estimated_pipeline": "£46,200.00",
            "converted_value": "£28,400.00",
        },
    }
    return render(request, "web/backoffice/bulk_orders.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def pos(request):
    categories = [
        "All Products",
        "Rice & Grains",
        "Lentils & Pulses",
        "Spices",
        "Oils & Ghee",
        "Tea & Beverages",
    ]
    pos_products = [
        {
            "name": "Himalayan Basmati Rice",
            "sku": "TF-RICE-01",
            "category": "Rice & Grains",
            "price": "12.50",
            "weight": "5 kg",
            "stock": 45,
            "badge": "Popular",
        },
        {
            "name": "Organic Red Lentils (Masoor)",
            "sku": "TF-PULSE-02",
            "category": "Lentils & Pulses",
            "price": "4.20",
            "weight": "1 kg",
            "stock": 78,
            "badge": "Organic",
        },
        {
            "name": "Cold-Pressed Mustard Oil",
            "sku": "TF-OIL-03",
            "category": "Oils & Ghee",
            "price": "6.80",
            "weight": "1 L",
            "stock": 32,
            "badge": "Cold-Pressed",
        },
        {
            "name": "Wild Timut Pepper",
            "sku": "TF-SPICE-04",
            "category": "Spices",
            "price": "3.95",
            "weight": "100 g",
            "stock": 64,
            "badge": "Single Origin",
        },
        {
            "name": "Organic Black Cardamom",
            "sku": "TF-SPICE-05",
            "category": "Spices",
            "price": "5.50",
            "weight": "200 g",
            "stock": 29,
            "badge": "Aromatic",
        },
        {
            "name": "Pure Cow Ghee (Danedar)",
            "sku": "TF-GHEE-06",
            "category": "Oils & Ghee",
            "price": "11.90",
            "weight": "1 kg",
            "stock": 18,
            "badge": "Pure Dairy",
        },
        {
            "name": "Ilam Orthodox Black Tea",
            "sku": "TF-TEA-07",
            "category": "Tea & Beverages",
            "price": "7.25",
            "weight": "250 g",
            "stock": 52,
            "badge": "Himalayan",
        },
        {
            "name": "Flattened Rice (Chiura)",
            "sku": "TF-GRAIN-08",
            "category": "Rice & Grains",
            "price": "3.10",
            "weight": "1 kg",
            "stock": 40,
            "badge": "Crispy",
        },
        {
            "name": "Yellow Split Pigeon Peas",
            "sku": "TF-PULSE-09",
            "category": "Lentils & Pulses",
            "price": "4.50",
            "weight": "1 kg",
            "stock": 83,
            "badge": "High Protein",
        },
    ]
    context = {
        "active_page": "pos",
        "page_title": "POS",
        "categories": categories,
        "products": pos_products,
    }
    return render(request, "web/backoffice/pos.html", context)


@never_cache
@staff_member_required(login_url=reverse_lazy("backoffice:login"))
@require_safe
def products(request):
    catalog = [
        {
            "name": "Himalayan Basmati Rice",
            "category": "Rice & Grains",
            "sku": "TF-RICE-01",
            "stock": 185,
            "retail_price": "£12.50",
            "wholesale_price": "£9.50",
            "status": "In Stock",
        },
        {
            "name": "Organic Red Lentils (Masoor)",
            "category": "Lentils & Pulses",
            "sku": "TF-PULSE-02",
            "stock": 92,
            "retail_price": "£4.20",
            "wholesale_price": "£3.10",
            "status": "In Stock",
        },
        {
            "name": "Cold-Pressed Mustard Oil",
            "category": "Oils & Ghee",
            "sku": "TF-OIL-03",
            "stock": 4,
            "retail_price": "£6.80",
            "wholesale_price": "£5.20",
            "status": "Low Stock",
        },
        {
            "name": "Pure Cow Ghee (Danedar)",
            "category": "Oils & Ghee",
            "sku": "TF-GHEE-06",
            "stock": 18,
            "retail_price": "£11.90",
            "wholesale_price": "£9.20",
            "status": "In Stock",
        },
        {
            "name": "Wild Himalayan Timut Pepper",
            "category": "Spices",
            "sku": "TF-SPICE-04",
            "stock": 64,
            "retail_price": "£3.95",
            "wholesale_price": "£2.80",
            "status": "In Stock",
        },
        {
            "name": "Organic Black Cardamom",
            "category": "Spices",
            "sku": "TF-SPICE-05",
            "stock": 0,
            "retail_price": "£5.50",
            "wholesale_price": "£4.10",
            "status": "Out of Stock",
        },
        {
            "name": "Ilam Orthodox High Mountain Tea",
            "category": "Tea & Beverages",
            "sku": "TF-TEA-07",
            "stock": 52,
            "retail_price": "£7.25",
            "wholesale_price": "£5.60",
            "status": "In Stock",
        },
        {
            "name": "Nepali Beaten Rice (Chiura)",
            "category": "Rice & Grains",
            "sku": "TF-GRAIN-08",
            "stock": 75,
            "retail_price": "£3.10",
            "wholesale_price": "£2.30",
            "status": "In Stock",
        },
    ]
    context = {
        "active_page": "products",
        "page_title": "Products",
        "products_list": catalog,
        "stats": {
            "total": 64,
            "low_stock": 4,
            "out_of_stock": 1,
            "categories": 8,
        },
    }
    return render(request, "web/backoffice/products.html", context)


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
    customers_list = [
        {
            "name": "Priya Sharma",
            "email": "priya.sharma@example.co.uk",
            "phone": "+44 7700 900142",
            "tier": "Retail Customer",
            "orders_count": 6,
            "total_spent": "£168.50",
            "status": "Active",
            "joined": "12 Aug 2026",
        },
        {
            "name": "Himalayan Spice Bistro",
            "email": "procurement@himalayanspice.co.uk",
            "phone": "+44 113 496 0880",
            "tier": "Wholesale Tier 2 (Gold)",
            "orders_count": 19,
            "total_spent": "£3,840.00",
            "status": "Active",
            "joined": "04 May 2026",
        },
        {
            "name": "Sunil Thapa",
            "email": "sunil.thapa@example.co.uk",
            "phone": "+44 7700 900389",
            "tier": "Retail Customer",
            "orders_count": 4,
            "total_spent": "£82.40",
            "status": "Active",
            "joined": "29 Sep 2026",
        },
        {
            "name": "Kathmandu Kitchen London",
            "email": "chef@kathmandukitchen.co.uk",
            "phone": "+44 20 7946 0912",
            "tier": "Restaurant Partner",
            "orders_count": 28,
            "total_spent": "£5,920.00",
            "status": "Active",
            "joined": "18 Jan 2026",
        },
        {
            "name": "Aarav Patel",
            "email": "aarav.patel@example.co.uk",
            "phone": "+44 7700 900761",
            "tier": "Wholesale Tier 1 (Silver)",
            "orders_count": 8,
            "total_spent": "£940.00",
            "status": "Active",
            "joined": "14 Jul 2026",
        },
        {
            "name": "Anita Gurung",
            "email": "anita.gurung@example.co.uk",
            "phone": "+44 7700 900503",
            "tier": "Retail Customer",
            "orders_count": 3,
            "total_spent": "£64.20",
            "status": "Active",
            "joined": "01 Oct 2026",
        },
    ]
    context = {
        "active_page": "customers",
        "page_title": "Customers",
        "customers_list": customers_list,
        "stats": {
            "total": 1240,
            "wholesale": 84,
            "repeat_rate": "46.2%",
            "ltv": "£310.00",
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
