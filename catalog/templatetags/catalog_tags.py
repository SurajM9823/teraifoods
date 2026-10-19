from django import template

register = template.Library()


@register.simple_tag
def category_label(categories, key, child_slug=''):
    for category in categories:
        if category['filter_key'] == key:
            if not child_slug:
                return category['name']
            for child in category['subcategories']:
                if child['slug'] == child_slug:
                    return child['name']
    return ''
