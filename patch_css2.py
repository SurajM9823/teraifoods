import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product-detail.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# The file is CRLF. Read with newline='' preserves \r\n literally.
# Now search for the CSS block using \r\n

OLD_CSS = "\t\t.pdp-delivery-col {\r\n\t\t\twidth: 300px;\r\n\t\t\tflex: 0 0 300px;\r\n\t\t\tborder-left: 1px solid #f1f5f9;\r\n\t\t\tpadding-left: 18px;\r\n\t\t}\r\n\t\t.pdp-box-header {\r\n\t\t\tfont-size: 12px;\r\n\t\t\tfont-weight: 700;\r\n\t\t\ttext-transform: uppercase;\r\n\t\t\tcolor: #94a3b8;\r\n\t\t\tletter-spacing: 0.5px;\r\n\t\t\tmargin-bottom: 10px;\r\n\t\t\tdisplay: flex;\r\n\t\t\talign-items: center;\r\n\t\t\tjustify-content: space-between;\r\n\t\t}\r\n\t\t.pdp-delivery-item {\r\n\t\t\tdisplay: flex;\r\n\t\t\tgap: 10px;\r\n\t\t\tmargin-bottom: 12px;\r\n\t\t\tfont-size: 12.5px;\r\n\t\t}\r\n\t\t.pdp-delivery-item i {\r\n\t\t\tcolor: #64748b;\r\n\t\t\tfont-size: 15px;\r\n\t\t\tmargin-top: 2px;\r\n\t\t}\r\n\t\t.pdp-delivery-details {\r\n\t\t\tflex: 1;\r\n\t\t}\r\n\t\t.pdp-delivery-details .title {\r\n\t\t\tcolor: #0f172a;\r\n\t\t\tfont-weight: 600;\r\n\t\t\tdisplay: flex;\r\n\t\t\talign-items: center;\r\n\t\t\tjustify-content: space-between;\r\n\t\t}\r\n\t\t.pdp-delivery-details .change-link {\r\n\t\t\tcolor: #3b82f6;\r\n\t\t\tfont-size: 11.5px;\r\n\t\t\tfont-weight: 600;\r\n\t\t\ttext-decoration: none;\r\n\t\t}\r\n\t\t.pdp-delivery-details .sub {\r\n\t\t\tcolor: #64748b;\r\n\t\t\tfont-size: 13px;\r\n\t\t\tfont-weight: 600;\r\n\t\t\tmargin-top: 5px;\r\n\t\t\tpadding: 5px 8px;\r\n\t\t\tborder-radius: 4px;\r\n\t\t\tbackground: #f0fdfa;\r\n\t\t\tcolor: #0f766e;\r\n\t\t}\r\n\t\t.pdp-delivery-details .price {\r\n\t\t\tcolor: #0f172a;\r\n\t\t\tfont-weight: 700;\r\n\t\t}\r\n\t\t.pdp-divider {\r\n\t\t\theight: 1px;\r\n\t\t\tbackground: #f1f5f9;\r\n\t\t\tmargin: 14px 0;\r\n\t\t}\r\n\r\n\t\t/* QR Box */\r\n\t\t.pdp-qr-card {\r\n\t\t\tbackground: #f8fafc;\r\n\t\t\tborder: 1px dashed #cbd5e1;\r\n\t\t\tborder-radius: 4px;\r\n\t\t\tpadding: 10px;\r\n\t\t\tdisplay: flex;\r\n\t\t\talign-items: center;\r\n\t\t\tgap: 10px;\r\n\t\t\tmargin-bottom: 16px;\r\n\t\t}\r\n\t\t.pdp-qr-code {\r\n\t\t\twidth: 48px;\r\n\t\t\theight: 48px;\r\n\t\t\tbackground: #ffffff;\r\n\t\t\tborder: 1px solid #e2e8f0;\r\n\t\t\tpadding: 2px;\r\n\t\t\tborder-radius: 3px;\r\n\t\t}\r\n\t\t.pdp-qr-code img {\r\n\t\t\twidth: 100%;\r\n\t\t\theight: 100%;\r\n\t\t}\r\n\t\t.pdp-qr-text {\r\n\t\t\tfont-size: 11px;\r\n\t\t\tcolor: #64748b;\r\n\t\t\tline-height: 1.35;\r\n\t\t}\r\n\t\t.pdp-qr-text strong {\r\n\t\t\tcolor: #0f172a;\r\n\t\t\tdisplay: block;\r\n\t\t\tfont-size: 11.5px;\r\n\t\t}\r\n\r\n\t\t/* Seller Box */\r\n\t\t.pdp-seller-card {\r\n\t\t\tbackground: #fafafa;\r\n\t\t\tborder: 1px solid #f1f5f9;\r\n\t\t\tborder-radius: 4px;\r\n\t\t\tpadding: 12px;\r\n\t\t}\r\n\t\t.pdp-seller-title {\r\n\t\t\tfont-size: 11.5px;\r\n\t\t\tcolor: #94a3b8;\r\n\t\t\ttext-transform: uppercase;\r\n\t\t\tfont-weight: 600;\r\n\t\t\tmargin-bottom: 4px;\r\n\t\t}\r\n\t\t.pdp-seller-name {\r\n\t\t\tfont-size: 14px;\r\n\t\t\tfont-weight: 700;\r\n\t\t\tcolor: #0f172a;\r\n\t\t\tmargin-bottom: 10px;\r\n\t\t}\r\n\t\t.pdp-seller-stats {\r\n\t\t\tdisplay: flex;\r\n\t\t\ttext-align: center;\r\n\t\t\tborder-top: 1px solid #e2e8f0;\r\n\t\t\tborder-bottom: 1px solid #e2e8f0;\r\n\t\t\tpadding: 8px 0;\r\n\t\t\tmargin-bottom: 10px;\r\n\t\t}\r\n\t\t.pdp-seller-stat-col {\r\n\t\t\tflex: 1;\r\n\t\t\tborder-right: 1px solid #f1f5f9;\r\n\t\t}\r\n\t\t.pdp-seller-stat-col:last-child {\r\n\t\t\tborder-right: none;\r\n\t\t}\r\n\t\t.pdp-stat-label {\r\n\t\t\tfont-size: 10px;\r\n\t\t\tcolor: #64748b;\r\n\t\t\ttext-transform: uppercase;\r\n\t\t\tline-height: 1.2;\r\n\t\t}\r\n\t\t.pdp-stat-value {\r\n\t\t\tfont-size: 15px;\r\n\t\t\tfont-weight: 700;\r\n\t\t\tcolor: #0f172a;\r\n\t\t\tmargin-top: 2px;\r\n\t\t}\r\n\t\t.pdp-btn-visit-store {\r\n\t\t\twidth: 100%;\r\n\t\t\theight: 32px;\r\n\t\t\tborder: 1px solid #3b82f6;\r\n\t\t\tbackground: #ffffff;\r\n\t\t\tcolor: #3b82f6;\r\n\t\t\tfont-size: 12px;\r\n\t\t\tfont-weight: 700;\r\n\t\t\tborder-radius: 3px;\r\n\t\t\tcursor: pointer;\r\n\t\t\ttext-transform: uppercase;\r\n\t\t\ttransition: all 0.15s ease;\r\n\t\t}\r\n\t\t.pdp-btn-visit-store:hover {\r\n\t\t\tbackground: #3b82f6;\r\n\t\t\tcolor: #ffffff;\r\n\t\t}"

NEW_CSS = "\t\t/* Delivery & Trust Info Strip */\r\n\t\t.pdp-info-strip {\r\n\t\t\tdisplay: flex;\r\n\t\t\talign-items: center;\r\n\t\t\tflex-wrap: wrap;\r\n\t\t\tgap: 0;\r\n\t\t\tbackground: #ffffff;\r\n\t\t\tborder: 1px solid #e2e8f0;\r\n\t\t\tborder-radius: 6px;\r\n\t\t\tpadding: 12px 20px;\r\n\t\t\tmargin-bottom: 16px;\r\n\t\t\tfont-size: 13px;\r\n\t\t\tcolor: #334155;\r\n\t\t}\r\n\t\t.pdp-strip-item {\r\n\t\t\tdisplay: inline-flex;\r\n\t\t\talign-items: center;\r\n\t\t\tgap: 7px;\r\n\t\t\tpadding: 4px 0;\r\n\t\t\tfont-weight: 500;\r\n\t\t}\r\n\t\t.pdp-strip-item i {\r\n\t\t\tcolor: #634c9f;\r\n\t\t\tfont-size: 15px;\r\n\t\t}\r\n\t\t.pdp-strip-divider {\r\n\t\t\twidth: 1px;\r\n\t\t\theight: 18px;\r\n\t\t\tbackground: #e2e8f0;\r\n\t\t\tmargin: 0 18px;\r\n\t\t}\r\n\t\t@media (max-width: 767px) {\r\n\t\t\t.pdp-info-strip { gap: 6px 0; padding: 10px 14px; }\r\n\t\t\t.pdp-strip-divider { display: none; }\r\n\t\t\t.pdp-strip-item { width: 50%; }\r\n\t\t}"

if OLD_CSS in content:
    content = content.replace(OLD_CSS, NEW_CSS, 1)
    print("CSS replaced OK")
else:
    print("MATCH FAILED - checking fragment...")
    # Try to find just the first part
    frag = "\t\t.pdp-delivery-col {\r\n\t\t\twidth: 300px;"
    idx = content.find(frag)
    print(f"  Fragment at: {idx}")
    if idx != -1:
        print(repr(content[idx:idx+80]))

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Written.")
