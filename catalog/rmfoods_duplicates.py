"""Conservative, repeatable matching without fuzzy names or pack-size guesses."""
import unicodedata


def identity(value):
    return ' '.join(unicodedata.normalize('NFKC', value or '').casefold().split())


class DuplicateIndex:
    def __init__(self, products=()):
        self.keys, self.names, self.skus = {}, {}, {}
        for product in products:
            self.add(product)

    def add(self, product):
        if product.get('legacy_key'):
            self.keys.setdefault(product['legacy_key'], product)
        if identity(product['name']):
            self.names.setdefault(identity(product['name']), product)
        if identity(product.get('sku')):
            self.skus.setdefault(identity(product['sku']), product)

    def find(self, product):
        for reason, index, key in (
            ('source_key', self.keys, product.get('legacy_key') or product.get('key')),
            ('name', self.names, identity(product['name'])),
            ('sku', self.skus, identity(product.get('sku')))):
            if key and key in index:
                return reason, index[key]
        return None, None
