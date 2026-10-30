import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'web/templates/web/product-detail.html'
with open(path, 'rb') as f:
    raw = f.read()

crlf = raw.count(b'\r\n')
lf = raw.count(b'\n') - crlf
print(f"CRLF: {crlf}, LF-only: {lf}")
print("First 200 bytes repr:", repr(raw[:200]))

# Check around the delivery-col css area
idx = raw.find(b'.pdp-delivery-col {')
if idx != -1:
    print("CSS area around .pdp-delivery-col:")
    print(repr(raw[idx:idx+100]))
