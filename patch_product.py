import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Lines 1857-1954 (0-indexed: 1856-1953) = pdp-delivery-col block
# Line 1955 is blank, 1956 closes pdp-main-row, 1957 closes pdp-main-card, 1958 is blank

DEL_START = 1856  # 0-indexed, <div class="pdp-delivery-col">
DEL_END = 1954    # 0-indexed exclusive (line 1954 = index 1953 is </div> closing col, so end = 1954)

print(f"Removing lines {DEL_START} to {DEL_END-1} (0-indexed):")
print(repr(lines[DEL_START][:80]))
print(repr(lines[DEL_END-1][:80]))
print(f"Line after (pdp-main-row close): {repr(lines[DEL_END][:80])}")

INFO_STRIP = '''\t\t\t\t\t\t<!-- Delivery & Trust Strip -->
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
\t\t\t\t\t\t</div>
'''

new_lines = lines[:DEL_START] + lines[DEL_END:]
print(f"\nAfter col removal: {len(new_lines)} lines")

# Now find where to insert strip (after pdp-main-card closes = after the two </div> lines)
# Looking at what follows DEL_START now:
for j in range(DEL_START, min(DEL_START+10, len(new_lines))):
    print(f"  [{j}]: {repr(new_lines[j][:80])}")

# Find the description section or next section after main card
insert_at = None
for i in range(DEL_START, min(DEL_START + 10, len(new_lines))):
    line = new_lines[i]
    if '<!-- 3.' in line or 'pdp-section-card' in line or 'description-section' in line:
        insert_at = i
        break

if insert_at is None:
    # Find blank line after the two closing divs
    for i in range(DEL_START, min(DEL_START+8, len(new_lines))):
        if new_lines[i].strip() == '' and i > DEL_START + 1:
            insert_at = i + 1
            break

print(f"\nInserting strip at index: {insert_at}")
if insert_at and insert_at < len(new_lines):
    print(f"  Before: {repr(new_lines[insert_at][:80])}")

if insert_at:
    new_lines = new_lines[:insert_at] + [INFO_STRIP] + new_lines[insert_at:]
    print("Strip inserted")

# Now do CSS replacement
new_content = ''.join(new_lines)

# product.html uses LF
OLD_CSS_BLOCK = (
    "\t\t.pdp-delivery-col {\n"
    "\t\t\twidth: 300px;\n"
    "\t\t\tflex: 0 0 300px;\n"
    "\t\t\tborder-left: 1px solid #f1f5f9;\n"
    "\t\t\tpadding-left: 18px;\n"
    "\t\t}\n"
    "\t\t.pdp-box-header {\n"
)

NEW_CSS_BLOCK = (
    "\t\t/* Delivery & Trust Info Strip */\n"
    "\t\t.pdp-info-strip {\n"
    "\t\t\tdisplay: flex;\n"
    "\t\t\talign-items: center;\n"
    "\t\t\tflex-wrap: wrap;\n"
    "\t\t\tgap: 0;\n"
    "\t\t\tbackground: #ffffff;\n"
    "\t\t\tborder: 1px solid #e2e8f0;\n"
    "\t\t\tborder-radius: 6px;\n"
    "\t\t\tpadding: 12px 20px;\n"
    "\t\t\tmargin-bottom: 16px;\n"
    "\t\t\tfont-size: 13px;\n"
    "\t\t\tcolor: #334155;\n"
    "\t\t}\n"
    "\t\t.pdp-strip-item {\n"
    "\t\t\tdisplay: inline-flex;\n"
    "\t\t\talign-items: center;\n"
    "\t\t\tgap: 7px;\n"
    "\t\t\tpadding: 4px 0;\n"
    "\t\t\tfont-weight: 500;\n"
    "\t\t}\n"
    "\t\t.pdp-strip-item i {\n"
    "\t\t\tcolor: #634c9f;\n"
    "\t\t\tfont-size: 15px;\n"
    "\t\t}\n"
    "\t\t.pdp-strip-divider {\n"
    "\t\t\twidth: 1px;\n"
    "\t\t\theight: 18px;\n"
    "\t\t\tbackground: #e2e8f0;\n"
    "\t\t\tmargin: 0 18px;\n"
    "\t\t}\n"
    "\t\t@media (max-width: 767px) {\n"
    "\t\t\t.pdp-info-strip { gap: 6px 0; padding: 10px 14px; }\n"
    "\t\t\t.pdp-strip-divider { display: none; }\n"
    "\t\t\t.pdp-strip-item { width: 50%; }\n"
    "\t\t}\n"
    "\t\t.pdp-box-header {\n"
)

# Also need to remove the qr-card, seller-card CSS and delivery-item CSS
# Find the start of the block in new_content
start_idx = new_content.find(OLD_CSS_BLOCK)
if start_idx != -1:
    # Replace just the delivery-col opener + box-header opener with our new CSS
    new_content = new_content.replace(OLD_CSS_BLOCK, NEW_CSS_BLOCK, 1)
    print("CSS block start replaced")
else:
    print("CSS block start NOT found")
    idx = new_content.find('.pdp-delivery-col {')
    print(f"  .pdp-delivery-col at: {idx}")
    if idx != -1:
        print(repr(new_content[idx:idx+80]))

# Find and remove: delivery-item, delivery-details, qr-card, seller-card CSS
# (box-header we keep for potential other uses, but remove seller/qr CSS)
# Find the QR Card CSS comment to end of seller block
old_qr_seller = (
    "\t\t/* QR Box */\n"
    "\t\t.pdp-qr-card {\n"
    "\t\t\tbackground: #f8fafc;\n"
    "\t\t\tborder: 1px dashed #cbd5e1;\n"
    "\t\t\tborder-radius: 4px;\n"
    "\t\t\tpadding: 10px;\n"
    "\t\t\tdisplay: flex;\n"
    "\t\t\talign-items: center;\n"
    "\t\t\tgap: 10px;\n"
    "\t\t\tmargin-bottom: 16px;\n"
    "\t\t}\n"
)

if old_qr_seller in new_content:
    new_content = new_content.replace(old_qr_seller, '', 1)
    print("Removed QR card CSS")
else:
    print("QR card CSS not found - checking...")
    idx = new_content.find('/* QR Box */')
    print(f"  /* QR Box */ at: {idx}")

# Remove media query delivery-col rules
old_mq1 = (
    "\n\t\t\t.pdp-delivery-col {\n"
    "\t\t\t\twidth: 100% !important;\n"
    "\t\t\t\tflex: 0 0 100% !important;\n"
    "\t\t\t\tborder-left: none !important;\n"
    "\t\t\t\tborder-top: 1px solid #f1f5f9 !important;\n"
    "\t\t\t\tpadding-left: 0 !important;\n"
    "\t\t\t\tpadding-top: 18px !important;\n"
    "\t\t\t\tmargin-top: 14px !important;\n"
    "\t\t\t\tdisplay: grid !important;\n"
    "\t\t\t\tgrid-template-columns: repeat(auto-fit, minmax(240px, 1fr)) !important;\n"
    "\t\t\t\tgap: 16px !important;\n"
    "\t\t\t}\n"
    "\t\t\t.pdp-delivery-col .pdp-divider {\n"
    "\t\t\t\tdisplay: none !important;\n"
    "\t\t\t}\n"
)

old_mq2 = (
    "\n\t\t\t.pdp-delivery-col {\n"
    "\t\t\t\tgrid-template-columns: 1fr !important;\n"
    "\t\t\t\tgap: 12px !important;\n"
    "\t\t\t}\n"
    "\t\t\t.pdp-delivery-col .pdp-divider {\n"
    "\t\t\t\tdisplay: block !important;\n"
    "\t\t\t}\n"
)

if old_mq1 in new_content:
    new_content = new_content.replace(old_mq1, '\n', 1)
    print("Removed MQ1 delivery-col")
else:
    print("MQ1 not found")
    idx = new_content.find('.pdp-delivery-col {\n\t\t\t\twidth: 100%')
    print(f"  MQ1 partial at: {idx}")

if old_mq2 in new_content:
    new_content = new_content.replace(old_mq2, '\n', 1)
    print("Removed MQ2 delivery-col")
else:
    print("MQ2 not found")

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(new_content)
print(f"Done. Written {len(new_content)} chars")
