import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product-detail.html'
with open(path, 'r', encoding='utf-8', newline='') as f:
    content = f.read()

# Remove the two pdp-delivery-col media query blocks:

# Block 1 (in ~1279.98px breakpoint)
OLD1 = "\r\n\t\t\t.pdp-delivery-col {\r\n\t\t\t\twidth: 100% !important;\r\n\t\t\t\tflex: 0 0 100% !important;\r\n\t\t\t\tborder-left: none !important;\r\n\t\t\t\tborder-top: 1px solid #f1f5f9 !important;\r\n\t\t\t\tpadding-left: 0 !important;\r\n\t\t\t\tpadding-top: 18px !important;\r\n\t\t\t\tmargin-top: 14px !important;\r\n\t\t\t\tdisplay: grid !important;\r\n\t\t\t\tgrid-template-columns: repeat(auto-fit, minmax(240px, 1fr)) !important;\r\n\t\t\t\tgap: 16px !important;\r\n\t\t\t}\r\n\t\t\t.pdp-delivery-col .pdp-divider {\r\n\t\t\t\tdisplay: none !important;\r\n\t\t\t}"

# Block 2 (in ~991.98px breakpoint)
OLD2 = "\r\n\t\t\t.pdp-delivery-col {\r\n\t\t\t\tgrid-template-columns: 1fr !important;\r\n\t\t\t\tgap: 12px !important;\r\n\t\t\t}\r\n\t\t\t.pdp-delivery-col .pdp-divider {\r\n\t\t\t\tdisplay: block !important;\r\n\t\t\t}"

changed = False
if OLD1 in content:
    content = content.replace(OLD1, '', 1)
    print("Removed delivery-col block 1 (1279px breakpoint)")
    changed = True
else:
    print("Block 1 not found")

if OLD2 in content:
    content = content.replace(OLD2, '', 1)
    print("Removed delivery-col block 2 (991px breakpoint)")
    changed = True
else:
    print("Block 2 not found")

if changed:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print("File written.")
