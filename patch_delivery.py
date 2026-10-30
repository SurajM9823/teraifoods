"""
Restructure delivery options in product-detail.html:
1. Remove the entire pdp-delivery-col from inside pdp-main-row
2. Replace with a horizontal info strip below the main card
3. Clean up CSS (remove green boxes, delivery col styles)
"""

path = r'web/templates/web/product-detail.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Remove the entire pdp-delivery-col block ─────────────────────────────
# From <div class="pdp-delivery-col"> all the way to its closing </div> (line 2440)
# We'll use a marker-based replacement

OLD_DELIVERY_COL = '''\t\t\t\t\t\t\t\t<div class="pdp-delivery-col">

\t\t\t\t\t\t\t\t\t{% if product.is_package %}
\t\t\t\t\t\t\t\t\t<!-- Package Savings Card -->
\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-summary-card">
\t\t\t\t\t\t\t\t\t\t<div class="pdp-box-header mb-2" style="border-bottom:1px solid #bbf7d0; padding-bottom:6px;">
\t\t\t\t\t\t\t\t\t\t\t<span class="fw-bold text-dark"><i class="klb-icon-gift text-success me-1"></i> Bundle Value Summary</span>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-math">
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-math-row">
\t\t\t\t\t\t\t\t\t\t\t\t<span>Combined Retail Value:</span>
\t\t\t\t\t\t\t\t\t\t\t\t<span><del>&pound;{{ product.base_price }}</del></span>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-math-row text-success fw-semibold">
\t\t\t\t\t\t\t\t\t\t\t\t<span>Package Discount ({{ product.discount_percent }}%):</span>
\t\t\t\t\t\t\t\t\t\t\t\t<span>-&pound;{{ product.bundle_savings }}</span>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-math-total">
\t\t\t\t\t\t\t\t\t\t\t\t<span>Special Bundle Price:</span>
\t\t\t\t\t\t\t\t\t\t\t\t<span class="deal-price">&pound;{{ product.price }}</span>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-bundle-savings-alert">
\t\t\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-check-circle"></i> You save <strong>&pound;{{ product.bundle_savings }}</strong> with this package!
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="pdp-divider"></div>
\t\t\t\t\t\t\t\t\t{% endif %}

\t\t\t\t\t\t\t\t\t<div class="pdp-box-header">
\t\t\t\t\t\t\t\t\t\t<span>Delivery Options</span>
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-info-circle text-muted"></i>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<!-- Location -->
\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-item">
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-map-pin"></i>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-details">
\t\t\t\t\t\t\t\t\t\t\t<div class="title">
\t\t\t\t\t\t\t\t\t\t\t\t<span>Whole United Kingdom</span>
\t\t\t\t\t\t\t\t\t\t\t\t<a href="#" class="change-link">CHANGE</a>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<!-- Standard Delivery -->
\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-item">
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-truck"></i>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-details">
\t\t\t\t\t\t\t\t\t\t\t<div class="title">
\t\t\t\t\t\t\t\t\t\t\t\t<span>Standard Delivery</span>
\t\t\t\t\t\t\t\t\t\t\t\t<span class="price">Calculated by basket weight</span>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="sub">Estimated {{ delivery_policy.minimum_days|default:2 }}\\u20134 days</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<!-- Cash / Card -->
\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-item">
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-credit-card"></i>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-details">
\t\t\t\t\t\t\t\t\t\t\t<div class="title">Secure card payment</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="sub">Continue to Stripe at checkout</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<div class="pdp-divider"></div>

\t\t\t\t\t\t\t\t\t<!-- Return & Warranty -->
\t\t\t\t\t\t\t\t\t<div class="pdp-box-header">
\t\t\t\t\t\t\t\t\t\t<span>Return &amp; Warranty</span>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-item">
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-refresh-cw"></i>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-details">
\t\t\t\t\t\t\t\t\t\t\t<div class="title">Return requests</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="sub">Request a return from your delivered order for review</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-item">
\t\t\t\t\t\t\t\t\t\t<i class="klb-icon-shield-check"></i>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-delivery-details">
\t\t\t\t\t\t\t\t\t\t\t<div class="title">100% Authentic Quality</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="sub">Please check the product label for origin and certification</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<div class="pdp-divider"></div>

\t\t\t\t\t\t\t\t\t<!-- QR Box -->
\t\t\t\t\t\t\t\t\t<div class="pdp-qr-card">
\t\t\t\t\t\t\t\t\t\t<div class="pdp-qr-code">
\t\t\t\t\t\t\t\t\t\t\t<picture>
\t\t\t\t\t\t\t\t\t\t\t\t<source type="image/webp" srcset="{% static 'web/images/terai_food_logo.webp' %}">
\t\t\t\t\t\t\t\t\t\t\t\t<img src="{% static 'web/images/terai_food_logo.png' %}" alt="Terai Food" loading="lazy" decoding="async">
\t\t\t\t\t\t\t\t\t\t\t</picture>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-qr-text">
\t\t\t\t\t\t\t\t\t\t\t<strong>Terai Foods</strong>
\t\t\t\t\t\t\t\t\t\t\tShop securely on our website
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t\t<!-- Seller Card -->
\t\t\t\t\t\t\t\t\t<div class="pdp-seller-card">
\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-title">Sold by</div>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-name">Terai Foods</div>
\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-stats">
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-stat-col">
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-label">Positive Seller Ratings</div>
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-value">\u2014</div>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-stat-col">
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-label">Ship on Time</div>
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-value">\u2014</div>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-seller-stat-col">
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-label">Chat Response Rate</div>
\t\t\t\t\t\t\t\t\t\t\t\t<div class="pdp-stat-value">\u2014</div>
\t\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t\t<button class="pdp-btn-visit-store" onclick="window.location.href='/shop/'">Visit Store</button>
\t\t\t\t\t\t\t\t\t</div>

\t\t\t\t\t\t\t\t</div>'''

# The new info strip that replaces it — inserted AFTER </div></div> closing pdp-main-card
INFO_STRIP_HTML = '''
\t\t\t\t\t\t<!-- Delivery & Trust Strip -->
\t\t\t\t\t\t<div class="pdp-info-strip">
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-map-pin"></i>
\t\t\t\t\t\t\t\t<span>Whole United Kingdom</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-truck"></i>
\t\t\t\t\t\t\t\t<span>Standard Delivery &mdash; 2&ndash;4 days</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-credit-card"></i>
\t\t\t\t\t\t\t\t<span>Secure Stripe card payment</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-refresh-cw"></i>
\t\t\t\t\t\t\t\t<span>Return requests available</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="pdp-strip-divider"></div>
\t\t\t\t\t\t\t<div class="pdp-strip-item">
\t\t\t\t\t\t\t\t<i class="klb-icon-shield-check"></i>
\t\t\t\t\t\t\t\t<span>100% Authentic Quality</span>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>'''

# The closing tags after pdp-delivery-col:
#   </div>  ← closes pdp-main-row
#   </div>  ← closes pdp-main-card
OLD_CLOSING = '''\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>

\t\t\t\t\t\t{% if product.is_package %}'''

NEW_CLOSING = '''\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>
''' + INFO_STRIP_HTML + '''

\t\t\t\t\t\t{% if product.is_package %}'''

# Step 1: Remove the delivery col
if OLD_DELIVERY_COL in content:
    content = content.replace(OLD_DELIVERY_COL, '', 1)
    print("✓ Removed pdp-delivery-col block")
else:
    print("✗ Could not find pdp-delivery-col block — checking partial match...")
    # Try to find it with actual file content
    idx = content.find('<div class="pdp-delivery-col">')
    print(f"  pdp-delivery-col found at char index: {idx}")
    if idx != -1:
        snippet = content[idx:idx+200]
        print("  Snippet:", repr(snippet))

# Step 2: Insert info strip after main card
if OLD_CLOSING in content:
    content = content.replace(OLD_CLOSING, NEW_CLOSING, 1)
    print("✓ Inserted pdp-info-strip after main card")
else:
    print("✗ Could not find closing tag sequence for main card")
    idx = content.find('\t\t\t\t\t\t\t</div>\n\t\t\t\t\t\t</div>')
    print(f"  Closing sequence found at: {idx}")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("✓ File written")
