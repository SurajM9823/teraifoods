with open('web/templates/web/product-detail.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
print('Total lines:', len(lines))
for i, l in enumerate(lines):
    if any(k in l for k in ['pdp-delivery-col', 'pdp-qr-card', 'pdp-seller-card', 'pdp-box-header', 'You may also like', 'pdp-main-card', 'pdp-info-strip', 'pdp-package-items']):
        print(f'{i+1}: {l}', end='')
