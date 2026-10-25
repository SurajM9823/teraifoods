"""Two-level merchandising taxonomy; source collections also include brands/promotions.

Menu groups checked against https://www.rmfoodswholesale.co.uk/ on 2026-10-25.
The local model has one category/subcategory, so Energy Drinks is its own main
category (as in the source menu), rather than a second assignment under Drinks.
Name-based recovery is flagged for review when the source supplies no useful type.
"""
import re
from dataclasses import dataclass
from django.utils.text import slugify

VERSION = 1

# Order resolves overlapping merchandise collections; brands never win over types.
# Each child has its display name and matching source collection aliases.
GROUPS = [
    ('Energy Drinks', ['Energy Drinks'], [
        ('Monster Energy', ['Monster Energy']), ('Red Bull', ['Red Bull']),
        ('Boost Energy', ['Boost Energy']), ('Rockstar Energy', ['Rockstar Energy', 'Rockstar']),
        ('Relentless Energy', ['Relentless Energy']), ('C4 Energy', ['C4 Energy']),
        ('Celsius Energy', ['Celsius']), ('Hell Energy', ['Hell Energy']),
        ('Urban Energy', ['Urban Energy']), ('Z-Energy', ['Z-Energy']),
        ('Lucozade Energy', ['Lucozade']), ('Other Energy Drinks', [])]),
    ('Coffee', ['Coffee', 'Coffee Sachets/Blends', 'Ready to Drink Coffee', 'Coffee Ground/Granules'], [
        ('Coffee Sachets / Blends', ['Coffee Sachets/Blends']),
        ('Ready to Drink Coffee', ['Ready to Drink Coffee']),
        ('Coffee Ground / Granules', ['Coffee Ground/Granules'])]),
    ('Crisps', ['Crisps'], [
        (name, [name]) for name in ('Walkers Crisps', "McCoy's Crisps", 'Smiths Crisps',
            'Pringles Crisps', 'Nik Naks', 'Discos', 'Wheat Crunchies', 'Burtons',
            'Golden Wonder Crisps', 'Jacobs Snacks', 'Doritos', 'Hula Hoops',
            'Walkers Quavers', 'Walkers Wotsits', 'Space Raiders', 'Other Crisps')]),
    ('Snacks & Chocolates', ['Confectionary', 'Bagged Sweets', 'Sweet Tubs', 'Chocolate Bars',
                            'Mints & Lozenges', 'Chewing Gum', 'Popcorn', 'Cereal/Snack Bars', 'Nuts'], [
        ('Cereal & Snack Bars', ['Cereal/Snack Bars']), ('Chewing Gum', ['Chewing Gum']),
        ('Mints & Lozenges', ['Mints & Lozenges']), ('Popcorn', ['Popcorn']),
        ('Sweet Tubs', ['Sweet Tubs']), ('Chocolate Bars', ['Chocolate Bars']),
        ('Bagged Sweets', ['Bagged Sweets']), ('Nuts & Savoury Snacks', ['Nuts'])]),
    ('Noodles', ['Noodles'], [(name, [name]) for name in ('Koka Noodles', 'Ko Lee Noodles',
        'Pot Noodles', 'Nissin Noodles', 'Blue Dragon', 'Maggi Noodles', 'Yumsu Noodles', 'Other Noodles')]),
    ('Drinks', ['Drinks', 'Soft Drinks', 'Water', 'Flavoured Water', 'Juices',
                'Sports Drinks / Isotonics', 'Sports Drinks', 'Milkshakes'], [
        ('Flavoured Water', ['Flavoured Water']), ('Water', ['Water']),
        ('Sports Drinks / Isotonics', ['Sports Drinks / Isotonics', 'Sports Drinks']),
        ('Milkshakes', ['Milkshakes']), ('Juices', ['Juices']), ('Soft Drinks', ['Soft Drinks']),
        ('Hot Chocolate & Malt Drinks', []), ('Drink Syrups & Purees', []), ('Other Drinks', [])]),
    ('Toiletries', ['Toiletries', 'Dental Care', 'Deodorants', 'Shower Products', 'Hair Products'], [
        ('Dental Care', ['Dental Care']), ('Deodorants', ['Deodorants']),
        ('Shower & Bath', ['Shower Products']), ('Hair Products', ['Hair Products']),
        ('Cotton Wool & Personal Care', [])]),
    ('Cleaning Products', ['Cleaning Products', 'Tissues'], [
        ('Tissues & Paper Products', ['Tissues']), ('Household Cleaning', [])]),
    ('Pet Foods', ['Pet Foods'], [('Cat Food & Treats', []), ('Dog Food & Treats', []), ('Pet Food & Treats', [])]),
    ('Cereals', ['Cereals', "Kellogg's Cereal", 'Nestle Cereal', 'Weetabix'], [('Breakfast Cereals', [])]),
    ('Biscuits', ['Biscuits', "Mcvitie's Biscuits", "Fox's Biscuits", 'Maryland Cookies', "Oreo's"], [
        ('Biscuits & Cookies', []), ('Wafers & Cakes', [])]),
    ('Curry Sauces/Pastes', ['Curry Sauces/Pastes'], [('Curry Sauces & Cooking Pastes', [])]),
    ('Sauces', ['Sauces', 'Chilli Sauces', 'Crucials Sauces', 'Lion Sauces', 'Heinz Sauces',
                'Olympic Sauces', 'HP Sauces'], [
        ('Chilli Sauces', ['Chilli Sauces']), ('Crucials Sauces', ['Crucials Sauces']),
        ('Lion Sauces', ['Lion Sauces']), ('Heinz Sauces', ['Heinz Sauces']),
        ('Olympic Sauces', ['Olympic Sauces']), ('HP Sauces', ['HP Sauces']),
        ('Pasta Sauces', []), ('Mustard, Relish & Chutney', []), ('Other Sauces', [])]),
    ('Spices', ['Spices', 'Ground Spices', 'Whole Spices', 'Seasoning Mix'], [
        ('Ground Spices', ['Ground Spices']), ('Whole Spices', ['Whole Spices']),
        ('Seasoning Mix', ['Seasoning Mix']), ('Herbs, Salt & Seasonings', [])]),
    ('Lentils', ['Lentils'], [('Lentils, Beans & Pulses', [])]),
    ('Tea', ['Tea'], [('Tea Bags & Loose Tea', [])]),
    ('Biodegradable Containers', ['Biodegradable Containers'], [('Food Containers', [])]),
    ('Food Cupboard', ['Rice', 'Tinned Goods', 'Baking', 'Cooking Oils', 'Food Flavouring/Essence',
                       'Food Colours', 'Soups', 'Gravy/Gravy Mix'], [
        ('Rice', ['Rice']), ('Baking Ingredients', ['Baking', 'Food Flavouring/Essence', 'Food Colours']),
        ('Oils & Ghee', ['Cooking Oils']), ('Soups & Stock', ['Soups']),
        ('Gravy & Sauce Mixes', ['Gravy/Gravy Mix']), ('Tinned Goods', ['Tinned Goods']),
        ('Pasta', []), ('Spreads, Honey & Syrups', []), ('Milk & Coffee Whiteners', []),
        ('Cooking Ingredients', [])]),
]

DISPLAY_ORDER = ['Drinks', 'Energy Drinks', 'Crisps', 'Coffee', 'Snacks & Chocolates', 'Noodles',
                 'Sauces', 'Cereals', 'Biscuits', 'Cleaning Products', 'Toiletries',
                 'Biodegradable Containers', 'Lentils', 'Spices', 'Curry Sauces/Pastes',
                 'Pet Foods', 'Tea', 'Food Cupboard']


def canonical(value):
    return re.sub(r'\s+', ' ', value.strip()).casefold()


@dataclass(frozen=True)
class Assignment:
    category: str
    subcategory: str
    method: str
    review: bool = False

    @property
    def category_slug(self):
        return 'snacks-chocolates' if self.category == 'Snacks & Chocolates' else slugify(self.category)

    @property
    def subcategory_slug(self):
        return slugify(self.subcategory)


# These type cues recover missing source memberships and avoid brand-only mistakes.
# Restrict cues to the product name; descriptions often mention unrelated foods.
NAME_RULES = [
    (r'cotton wool', 'Toiletries', 'Cotton Wool & Personal Care'),
    (r'coffee\s*mate|coffee whitener|condensed milk|milk portions|dairies.*milk', 'Food Cupboard', 'Milk & Coffee Whiteners'),
    (r'chocolate spread|chocalate spread|hazelnut.*spread|peanut butter(?!.*pretzel)|pistachio cream|\bbiscoff spread\b|\bhoney\b|maple syrup', 'Food Cupboard', 'Spreads, Honey & Syrups'),
    (r'hot chocolate|drinking.*chocolate|cocoa powder|horlicks|sweetened hot chocolate', 'Drinks', 'Hot Chocolate & Malt Drinks'),
    (r'^monin\b', 'Drinks', 'Drink Syrups & Purees'),
    (r'milkshake powder', 'Drinks', 'Milkshakes'),
    (r'\b(?:fusilli|penne|spaghetti|macaroni|vermicelli)\b|pasta .n. sauce', 'Food Cupboard', 'Pasta'),
    (r'\bghee\b|cooking oil|edible mustard oil', 'Food Cupboard', 'Oils & Ghee'),
    (r'\bbouillon\b|\bsoup\b', 'Food Cupboard', 'Soups & Stock'),
    (r'\b(?:cheese|parsley|pepper) sauce mix\b', 'Food Cupboard', 'Gravy & Sauce Mixes'),
    (r'\b(?:batter|custard|jelly|breadcrumb|pizza base|pastry|sponge cake|ground almond|citric acid)', 'Food Cupboard', 'Baking Ingredients'),
    (r'\bstuffing\b|crispy fried onion|pappadom', 'Food Cupboard', 'Cooking Ingredients'),
    (r'\b(?:garlic|ginger).*paste\b', 'Curry Sauces/Pastes', 'Curry Sauces & Cooking Pastes'),
    (r'\b(?:mustard|chutney|vinegar)\b', 'Sauces', 'Mustard, Relish & Chutney'),
    (r'^dolmio\b|bolognese|tomato passata|tomato puree|heinz sundried', 'Sauces', 'Pasta Sauces'),
    (r'garlic granules|sea salt', 'Spices', 'Herbs, Salt & Seasonings'),
    (r'peach slices', 'Food Cupboard', 'Tinned Goods'),
    (r'dried mixed fruit', 'Food Cupboard', 'Baking Ingredients'),
    (r'\b(?:flapjacks?|eat natural)\b|sesame bites', 'Snacks & Chocolates', 'Cereal & Snack Bars'),
    (r'^original source\b', 'Toiletries', 'Shower & Bath'),
    (r'^sensodyne\b', 'Toiletries', 'Dental Care'),
]


def assign(row):
    names = {canonical(c['name']) for c in row['categories']}
    name = row['name'].casefold()
    # Only unambiguous corrections precede source types. Broad fallback words
    # such as "jelly" or "honey" must never move pet food or sweets into baking.
    corrections = [(r'iced coffee|frappuccino', 'Coffee', 'Ready to Drink Coffee'),
                   (r'nutella & go', 'Snacks & Chocolates', 'Chocolate Bars'),
                   (r'biscoff topping sauce', 'Sauces', 'Other Sauces'),
                   NAME_RULES[0], NAME_RULES[1], NAME_RULES[3],
                   (r'choc(?:olate|alate) spread|hazelnut.*spread|biscoff spread|pistachio cream',
                    'Food Cupboard', 'Spreads, Honey & Syrups'),
                   (r'edible mustard oil', 'Food Cupboard', 'Oils & Ghee')]
    for pattern, parent, child in corrections:
        if re.search(pattern, name):
            return Assignment(parent, child, 'product_type_rule', True)
    energy_brands = {canonical(alias) for child, aliases in GROUPS[0][2]
                     if child != 'Lucozade Energy' for alias in aliases}
    if 'drinks' in names and names.intersection(energy_brands):
        for child, aliases in GROUPS[0][2]:
            if names.intersection(map(canonical, aliases)):
                return Assignment('Energy Drinks', child, 'source_brand')
    for parent, aliases, children in GROUPS:
        if names.intersection(map(canonical, aliases)):
            for child, child_aliases in children:
                if names.intersection(map(canonical, child_aliases)):
                    return Assignment(parent, child, 'source_menu')
            child = infer_child(parent, name, names)
            return Assignment(parent, child, 'source_type')
    for pattern, parent, child in NAME_RULES:
        if re.search(pattern, name):
            return Assignment(parent, child, 'name_recovery', True)
    # Only use brand information after all explicit merchandise collections.
    for parent, aliases, children in GROUPS:
        for child, child_aliases in children:
            if names.intersection(map(canonical, child_aliases)):
                return Assignment(parent, child, 'source_brand')
    recovered = recover_name(name, names)
    if recovered:
        return Assignment(*recovered, 'name_recovery', True)
    return Assignment('Needs Category Review', 'Unclassified', 'unresolved', True)


def infer_child(parent, name, names):
    if parent == 'Coffee':
        if re.search(r'iced|frappuccino|cans?\b|bottles?\b|caff[eè] latte|espresso.*\bml\b', name):
            return 'Ready to Drink Coffee'
        if re.search(r'sachet|sticks|3.?in.?1|2.?in.?1|cappuccino|latte', name):
            return 'Coffee Sachets / Blends'
        return 'Coffee Ground / Granules'
    if parent == 'Drinks':
        if re.search(r'water|smartwater', name):
            return 'Flavoured Water' if re.search(r'flavour|touch of|spring.*(?:berry|mango)', name) else 'Water'
        if re.search(r'isotonic|\bsport\b|powerade|hydrate', name):
            return 'Sports Drinks / Isotonics'
        if re.search(r'juice|ribena|robinsons|simply fruity', name):
            return 'Juices'
        if re.search(r'milkshake|yazoo|nurishment', name):
            return 'Milkshakes'
        return 'Soft Drinks'
    if parent == 'Pet Foods':
        if re.search(r'\bcat|kitten|whiskas|felix|sheba|go.cat|dreamies|gourmet perle', name):
            return 'Cat Food & Treats'
        if re.search(r'\bdog|puppy|pedigree|bakers|winalot|wagg|harrington', name):
            return 'Dog Food & Treats'
        return 'Pet Food & Treats'
    defaults = {'Energy Drinks': 'Other Energy Drinks', 'Crisps': 'Other Crisps',
                'Snacks & Chocolates': 'Chocolate Bars' if 'choc' in name else 'Bagged Sweets',
                'Noodles': 'Other Noodles', 'Toiletries': 'Cotton Wool & Personal Care',
                'Cleaning Products': 'Household Cleaning', 'Cereals': 'Breakfast Cereals',
                'Biscuits': 'Biscuits & Cookies', 'Sauces': 'Other Sauces',
                'Spices': 'Herbs, Salt & Seasonings', 'Lentils': 'Lentils, Beans & Pulses',
                'Tea': 'Tea Bags & Loose Tea', 'Biodegradable Containers': 'Food Containers',
                'Curry Sauces/Pastes': 'Curry Sauces & Cooking Pastes', 'Food Cupboard': 'Cooking Ingredients'}
    return defaults[parent]


def recover_name(name, names):
    if re.search(r'cereal|alpen\b', name):
        return 'Cereals', 'Breakfast Cereals'
    if re.search(r'coffee|nescafe|cappuccino|latte', name) or 'nescafe' in names:
        return 'Coffee', infer_child('Coffee', name, names)
    if re.search(r'coca.cola|pepsi|smartwater|glaceau', name):
        return 'Drinks', infer_child('Drinks', name, names)
    if re.search(r'\brice\b', name):
        return 'Food Cupboard', 'Rice'
    if re.search(r'biscuits?|cookies|\bbiscoff\b|\bwafer|tea cakes|snowballs|kinder cards|delice', name):
        return 'Biscuits', 'Wafers & Cakes' if re.search(r'wafer|cakes|snowballs|delice', name) else 'Biscuits & Cookies'
    if re.search(r'pretzels', name):
        return 'Snacks & Chocolates', 'Nuts & Savoury Snacks'
    if re.search(r'choc|ferrero|rafaello|kinder|terry.s|smarties|\bchoc dips\b', name):
        return 'Snacks & Chocolates', 'Chocolate Bars'
    if re.search(r'candy|bazooka|push pop', name):
        return 'Snacks & Chocolates', 'Bagged Sweets'
    if re.search(r'sauce|relish|topping', name):
        return 'Sauces', 'Other Sauces'
    return None


def collection_flags(row):
    names = {canonical(c['name']) for c in row['categories']}
    return {'best_offers': 'best offers' in names, 'most_popular': 'most popular' in names}


def mapped_metadata(row, assignment, existing=None):
    metadata = dict(existing if existing is not None else row.get('metadata', {}))
    flags = [flag for flag in metadata.get('review_required', [])
             if flag not in ('category_assignment_review', 'category_inferred_from_name')]
    if assignment.review:
        flags.append('category_inferred_from_name')
    metadata.update(
        review_required=list(dict.fromkeys(flags)),
        category_assignment='source menu hierarchy with explicit product type recovery',
        rmfoods_taxonomy={'version': VERSION, 'category': assignment.category,
                         'subcategory': assignment.subcategory, 'method': assignment.method,
                         'review_required': assignment.review},
        rmfoods_collections=collection_flags(row))
    return metadata


def resolve(assignment):
    """Reuse your category/subcategory records, including their inactive status."""
    from catalog.models import Category, Subcategory
    category = (Category.objects.filter(slug=assignment.category_slug).first() or
                Category.objects.filter(name__iexact=assignment.category).first())
    if category is None:
        position = DISPLAY_ORDER.index(assignment.category) if assignment.category in DISPLAY_ORDER else 100
        category = Category(name=assignment.category, slug=assignment.category_slug,
                            legacy_key='rm:taxonomy:' + assignment.category_slug, position=position)
        category.full_clean()
        category.save()
    child = (Subcategory.objects.filter(category=category, name__iexact=assignment.subcategory).first() or
             Subcategory.objects.filter(category=category, slug=assignment.subcategory_slug).first())
    if child is None:
        child = Subcategory(category=category, name=assignment.subcategory, slug=assignment.subcategory_slug)
        child.full_clean()
        child.save()
    return category, child
