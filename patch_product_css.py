import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Replace the delivery-col CSS opener (which differs from product-detail.html)
OLD = (
    "\t\t.pdp-delivery-col {\n"
    "\t\t\twidth: 310px;\n"
    "\t\t\tflex: 0 0 310px;\n"
    "\t\t\tborder-left: 1px solid #f1f5f9;\n"
    "\t\t\tpadding-left: 20px;\n"
    "\t\t}\n"
    "\t\t.pdp-box-header {\n"
    "\t\t\tfont-size: 12px;\n"
    "\t\t\tfont-weight: 700;\n"
    "\t\t\ttext-transform: uppercase;\n"
    "\t\t\tcolor: #94a3b8;\n"
    "\t\t\tletter-spacing: 0.5px;\n"
    "\t\t\tmargin-bottom: 10px;\n"
    "\t\t\tdisplay: flex;\n"
    "\t\t\talign-items: center;\n"
    "\t\t\tjustify-content: space-between;\n"
    "\t\t}\n"
    "\t\t.pdp-delivery-item {\n"
    "\t\t\tdisplay: flex;"
)

NEW = (
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
    "\t\t/* Delivery item styles (unused but kept for compat) */\n"
    "\t\t.pdp-delivery-item {\n"
    "\t\t\tdisplay: flex;"
)

if OLD in content:
    content = content.replace(OLD, NEW, 1)
    print("CSS replaced OK")
else:
    print("NOT FOUND")
    idx = content.find('.pdp-delivery-col {')
    print(f"idx={idx}, repr={repr(content[idx:idx+60])}")

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Written.")
