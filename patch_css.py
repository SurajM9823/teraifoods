import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product-detail.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Replace entire delivery-col CSS block with info-strip CSS ─────────────
OLD_CSS = """\t\t.pdp-delivery-col {\r
\t\t\twidth: 300px;\r
\t\t\tflex: 0 0 300px;\r
\t\t\tborder-left: 1px solid #f1f5f9;\r
\t\t\tpadding-left: 18px;\r
\t\t}\r
\t\t.pdp-box-header {\r
\t\t\tfont-size: 12px;\r
\t\t\tfont-weight: 700;\r
\t\t\ttext-transform: uppercase;\r
\t\t\tcolor: #94a3b8;\r
\t\t\tletter-spacing: 0.5px;\r
\t\t\tmargin-bottom: 10px;\r
\t\t\tdisplay: flex;\r
\t\t\talign-items: center;\r
\t\t\tjustify-content: space-between;\r
\t\t}\r
\t\t.pdp-delivery-item {\r
\t\t\tdisplay: flex;\r
\t\t\tgap: 10px;\r
\t\t\tmargin-bottom: 12px;\r
\t\t\tfont-size: 12.5px;\r
\t\t}\r
\t\t.pdp-delivery-item i {\r
\t\t\tcolor: #64748b;\r
\t\t\tfont-size: 15px;\r
\t\t\tmargin-top: 2px;\r
\t\t}\r
\t\t.pdp-delivery-details {\r
\t\t\tflex: 1;\r
\t\t}\r
\t\t.pdp-delivery-details .title {\r
\t\t\tcolor: #0f172a;\r
\t\t\tfont-weight: 600;\r
\t\t\tdisplay: flex;\r
\t\t\talign-items: center;\r
\t\t\tjustify-content: space-between;\r
\t\t}\r
\t\t.pdp-delivery-details .change-link {\r
\t\t\tcolor: #3b82f6;\r
\t\t\tfont-size: 11.5px;\r
\t\t\tfont-weight: 600;\r
\t\t\ttext-decoration: none;\r
\t\t}\r
\t\t.pdp-delivery-details .sub {\r
\t\t\tcolor: #64748b;\r
\t\t\tfont-size: 13px;\r
\t\t\tfont-weight: 600;\r
\t\t\tmargin-top: 5px;\r
\t\t\tpadding: 5px 8px;\r
\t\t\tborder-radius: 4px;\r
\t\t\tbackground: #f0fdfa;\r
\t\t\tcolor: #0f766e;\r
\t\t}\r
\t\t.pdp-delivery-details .price {\r
\t\t\tcolor: #0f172a;\r
\t\t\tfont-weight: 700;\r
\t\t}\r
\t\t.pdp-divider {\r
\t\t\theight: 1px;\r
\t\t\tbackground: #f1f5f9;\r
\t\t\tmargin: 14px 0;\r
\t\t}\r
\r
\t\t/* QR Box */\r
\t\t.pdp-qr-card {\r
\t\t\tbackground: #f8fafc;\r
\t\t\tborder: 1px dashed #cbd5e1;\r
\t\t\tborder-radius: 4px;\r
\t\t\tpadding: 10px;\r
\t\t\tdisplay: flex;\r
\t\t\talign-items: center;\r
\t\t\tgap: 10px;\r
\t\t\tmargin-bottom: 16px;\r
\t\t}\r
\t\t.pdp-qr-code {\r
\t\t\twidth: 48px;\r
\t\t\theight: 48px;\r
\t\t\tbackground: #ffffff;\r
\t\t\tborder: 1px solid #e2e8f0;\r
\t\t\tpadding: 2px;\r
\t\t\tborder-radius: 3px;\r
\t\t}\r
\t\t.pdp-qr-code img {\r
\t\t\twidth: 100%;\r
\t\t\theight: 100%;\r
\t\t}\r
\t\t.pdp-qr-text {\r
\t\t\tfont-size: 11px;\r
\t\t\tcolor: #64748b;\r
\t\t\tline-height: 1.35;\r
\t\t}\r
\t\t.pdp-qr-text strong {\r
\t\t\tcolor: #0f172a;\r
\t\t\tdisplay: block;\r
\t\t\tfont-size: 11.5px;\r
\t\t}\r
\r
\t\t/* Seller Box */\r
\t\t.pdp-seller-card {\r
\t\t\tbackground: #fafafa;\r
\t\t\tborder: 1px solid #f1f5f9;\r
\t\t\tborder-radius: 4px;\r
\t\t\tpadding: 12px;\r
\t\t}\r
\t\t.pdp-seller-title {\r
\t\t\tfont-size: 11.5px;\r
\t\t\tcolor: #94a3b8;\r
\t\t\ttext-transform: uppercase;\r
\t\t\tfont-weight: 600;\r
\t\t\tmargin-bottom: 4px;\r
\t\t}\r
\t\t.pdp-seller-name {\r
\t\t\tfont-size: 14px;\r
\t\t\tfont-weight: 700;\r
\t\t\tcolor: #0f172a;\r
\t\t\tmargin-bottom: 10px;\r
\t\t}\r
\t\t.pdp-seller-stats {\r
\t\t\tdisplay: flex;\r
\t\t\ttext-align: center;\r
\t\t\tborder-top: 1px solid #e2e8f0;\r
\t\t\tborder-bottom: 1px solid #e2e8f0;\r
\t\t\tpadding: 8px 0;\r
\t\t\tmargin-bottom: 10px;\r
\t\t}\r
\t\t.pdp-seller-stat-col {\r
\t\t\tflex: 1;\r
\t\t\tborder-right: 1px solid #f1f5f9;\r
\t\t}\r
\t\t.pdp-seller-stat-col:last-child {\r
\t\t\tborder-right: none;\r
\t\t}\r
\t\t.pdp-stat-label {\r
\t\t\tfont-size: 10px;\r
\t\t\tcolor: #64748b;\r
\t\t\ttext-transform: uppercase;\r
\t\t\tline-height: 1.2;\r
\t\t}\r
\t\t.pdp-stat-value {\r
\t\t\tfont-size: 15px;\r
\t\t\tfont-weight: 700;\r
\t\t\tcolor: #0f172a;\r
\t\t\tmargin-top: 2px;\r
\t\t}\r
\t\t.pdp-btn-visit-store {\r
\t\t\twidth: 100%;\r
\t\t\theight: 32px;\r
\t\t\tborder: 1px solid #3b82f6;\r
\t\t\tbackground: #ffffff;\r
\t\t\tcolor: #3b82f6;\r
\t\t\tfont-size: 12px;\r
\t\t\tfont-weight: 700;\r
\t\t\tborder-radius: 3px;\r
\t\t\tcursor: pointer;\r
\t\t\ttext-transform: uppercase;\r
\t\t\ttransition: all 0.15s ease;\r
\t\t}\r
\t\t.pdp-btn-visit-store:hover {\r
\t\t\tbackground: #3b82f6;\r
\t\t\tcolor: #ffffff;\r
\t\t}"""

NEW_CSS = """\t\t/* Delivery & Trust Info Strip */\r
\t\t.pdp-info-strip {\r
\t\t\tdisplay: flex;\r
\t\t\talign-items: center;\r
\t\t\tflex-wrap: wrap;\r
\t\t\tgap: 0;\r
\t\t\tbackground: #ffffff;\r
\t\t\tborder: 1px solid #e2e8f0;\r
\t\t\tborder-radius: 6px;\r
\t\t\tpadding: 12px 20px;\r
\t\t\tmargin-bottom: 16px;\r
\t\t\tfont-size: 13px;\r
\t\t\tcolor: #334155;\r
\t\t}\r
\t\t.pdp-strip-item {\r
\t\t\tdisplay: inline-flex;\r
\t\t\talign-items: center;\r
\t\t\tgap: 7px;\r
\t\t\tpadding: 4px 0;\r
\t\t\tfont-weight: 500;\r
\t\t}\r
\t\t.pdp-strip-item i {\r
\t\t\tcolor: #634c9f;\r
\t\t\tfont-size: 15px;\r
\t\t}\r
\t\t.pdp-strip-divider {\r
\t\t\twidth: 1px;\r
\t\t\theight: 18px;\r
\t\t\tbackground: #e2e8f0;\r
\t\t\tmargin: 0 18px;\r
\t\t}\r
\t\t@media (max-width: 767px) {\r
\t\t\t.pdp-info-strip { gap: 6px 0; }\r
\t\t\t.pdp-strip-divider { display: none; }\r
\t\t\t.pdp-strip-item { width: 50%; }\r
\t\t}"""

if OLD_CSS in content:
    content = content.replace(OLD_CSS, NEW_CSS, 1)
    print("CSS replaced successfully")
else:
    print("Could not find exact CSS block, trying partial detection...")
    idx = content.find('.pdp-delivery-col {')
    print(f"  .pdp-delivery-col found at char: {idx}")
    if idx != -1:
        print(repr(content[idx:idx+60]))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done.")
