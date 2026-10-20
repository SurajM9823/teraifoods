"""Apply data-only hooks to approved page templates and the existing engine."""
import re
from pathlib import Path
from extract_catalog import ROOT, Parser


for name in ('product-detail', 'product'):
    path = ROOT / f'web/templates/web/{name}.html'
    source = path.read_text(encoding='utf-8')
    parser = Parser(source)
    replacements = []
    fields = {
        'pdp-product-title':'{{ product.name }}',
        'pdp-main-price':'&pound;{{ product.price }}',
        'pdp-strike-price':'{% if product.sale_price %}<del>&pound;{{ product.regular_price }}</del> <span class="pdp-discount-pill">-{{ product.discount_percent }}%</span>{% endif %}',
        'pdp-stock-text':'{% if product.stock_confirmed %}{{ product.stock }} items available{% else %}Stock awaiting confirmation{% endif %}',
    }
    for node in parser.root.all():
        for cls, value in fields.items():
            if node.has(cls):
                replacements.append((node.open_end,node.close_start,value))
        if node.attrs.get('id') == 'pdp-active-image':
            raw = source[node.start:node.open_end]
            raw = re.sub(r'src="[^"]*"', 'src="{{ product.image_url }}"', raw)
            raw = re.sub(r'alt="[^"]*"', 'alt="{{ product.name }}"', raw)
            replacements.append((node.start,node.open_end,raw))
        if node.attrs.get('id') == 'pdp-thumbs-list':
            raw = '{% for image in product.images.all %}<div class="pdp-thumb-item{% if image.is_main %} active{% endif %}" data-img="{{ image.url }}"><img src="{{ image.url }}" alt="{{ image.alt }}" loading="lazy"></div>{% endfor %}'
            replacements.append((node.open_end,node.close_start,raw))
        if node.has('pdp-narrative'):
            # Retain the banner container and classes, parameterize prose only.
            paragraphs = [n for n in node.children if n.tag == 'p']
            if paragraphs:
                replacements.append((paragraphs[0].start,paragraphs[-1].end,'{{ product.description|linebreaks }}'))
        if node.has('pdp-brand-row'):
            replacements.append((node.open_end,node.close_start,'<a href="/shop/?category={{ product.category.slug }}">{{ product.category.name }}</a>'))
        if node.has('pdp-specs-grid'):
            replacements.append((node.open_end,node.close_start,'{% for spec in product.metadata.specifications %}<div class="pdp-spec-item"><span class="pdp-spec-bullet">&bull;</span> {{ spec }}</div>{% endfor %}'))
    for start,end,value in sorted(replacements,reverse=True):
        source = source[:start]+value+source[end:]
    source = source.replace('LAO GAN MA Tao Huabi Chilli Sauce With Chicken 280gm | Chinese Achar | Chilli Oil | Chicken Achar', '{{ product.name }}')
    source = source.replace('Only 14 items left, buy fast!', '{{ product.stock }} items available')
    source = source.replace('| 24 sold / 38 left', '| {{ product.stock }} available')
    # Existing handlers must defer to the catalog integration.
    source = source.replace("alert('Added ' + qty + ' bottle(s) of Lao Gan Ma Chicken Chilli Sauce to your cart!');", "window.TeraiCatalog?.addDetail(false);")
    source = source.replace("window.location.href = '/checkout/';", "window.TeraiCatalog?.addDetail(true);")
    source = source.replace('if (val < 14)', 'if (val < {{ product.stock|default:0 }})')
    source = source.replace('</body>', "{{ product_payload|json_script:'catalog-detail' }}\n</body>")
    path.write_text(source,encoding='utf-8')

path = ROOT / 'web/templates/web/shop.html'
source = path.read_text(encoding='utf-8')
# Keep category drawer behavior; replace only the local filtering algorithm.
start = source.index('\t\t\t// Storefront Elements')
end = source.index('\n\t\t});', start)
source = source[:start] + '\t\t\t// Filtering and pagination are provided by catalog-storefront.js.\n' + source[end:]
source = source.replace('</body>', "{{ catalog_page|json_script:'catalog-page' }}\n</body>")
path.write_text(source,encoding='utf-8')

path = ROOT / 'web/static/web/js/terai-interactive.js'
source = path.read_text(encoding='utf-8')
start = source.index('  // --- Default Wishlist Dataset')
end = source.index('  function saveWishlist', start)
source = source[:start] + '''  // Wishlists contain only products explicitly selected by this customer.
  function getWishlist() {
    try {
      const data = JSON.parse(localStorage.getItem(STORAGE_WISHLIST) || '[]');
      return Array.isArray(data) ? data.filter(item => item && typeof item === 'object' && item.id) : [];
    } catch { return []; }
  }

''' + source[end:]
source = source.replace("window.location.href = '/product-detail/';", "window.location.href = el.href || '/product-detail/';", 1)
source = source.replace("window.location.href = '/product-detail/';", "window.location.href = card.dataset.productUrl || '/product-detail/';", 1)
source = source.replace('getProductById(id) || catalog[0]', 'getProductById(id)')
# A single delegated handler handles appended database cards before old handlers.
source = source.replace('  function setupProductCardClicks() {', '''  function setupProductCardClicks() {
    window.TeraiCatalog = {refresh:indexProducts, addToCart, getProductById, openQuickview, showToast,
      getCart, saveCart, addDetail:window.TeraiCatalog?.addDetail};
    document.addEventListener('catalog:updated', indexProducts);''')
source = source.replace('  function addToCart(item, qty = 1) {', '''  function addToCart(item, qty = 1) {
    if (!item || !Number.isInteger(qty) || qty < 1) return;
    if (item.element?.dataset.catalogProduct && item.element.dataset.available !== 'true') {
      showToast('Unavailable', 'Stock must be confirmed before this item can be purchased.', 'warning');
      return;
    }''')
source = source.replace('quantity: qty\n', 'quantity: qty,\n        catalogVersion: 2\n')
source = source.replace("  function setupCategoryFiltering() {", "  function setupCategoryFiltering() {\n    if (document.querySelector('[data-catalog-product]')) return;")
# Backend catalog search is handled by the new script.
source = source.replace("  function setupLiveSearch() {", "  function setupLiveSearch() {\n    if (document.querySelector('script[src*=\"catalog-storefront\"]')) return;")
# Until a payment gateway is configured, do not manufacture paid order confirmations.
source = source.replace("sideCartDrawer.querySelector('#form-drawer-payment')?.addEventListener('submit', (e) => {",
"""sideCartDrawer.querySelector('#form-drawer-payment')?.addEventListener('submit', (e) => {
      e.preventDefault();
      showToast('Payment unavailable', 'Online payment is not configured. No payment has been taken.', 'warning');
      return;""")
path.write_text(source,encoding='utf-8')

# Availability is data, not a visual restyle.
for path in (ROOT / 'catalog/templates/catalog/storefront').glob('card_*.html'):
    source = path.read_text(encoding='utf-8').replace('data-catalog-product="{{ product.pk }}"',
        'data-catalog-product="{{ product.pk }}" data-available="{{ product.available|yesno:\'true,false\' }}"')
    path.write_text(source,encoding='utf-8')
print('Connected details and existing interaction engine; no customer CSS changed.')
