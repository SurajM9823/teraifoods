from django.db import migrations
from django.utils.text import slugify

# Frozen union of the original homepage, shop and product-page category lists.
ROWS = [{'name': 'Fruits & Vegetables',
  'slug': 'fruits-veg',
  'children': ['Cuts & Sprouts',
               'Exotic Fruits & Veggies',
               'Fresh Fruits',
               'Fresh Vegetables',
               'Herbs & Seasonings',
               'Packaged Produce',
               'Party Trays'],
  'menu_image': 'apple.svg'},
 {'name': 'Meats & Seafood',
  'slug': 'meats',
  'children': ['Beef Products',
               'Chicken and Turkey Products',
               'Fish Varieties',
               'Lamb Products',
               'Processed Red Meat Products',
               'Seafood',
               'Grass-Fed Lamb',
               'Himalayan River Trout'],
  'menu_image': 'meat.svg'},
 {'name': 'Breakfast & Dairy',
  'slug': 'breakfast',
  'children': ['Breads and Cereal Products',
               'Breakfast Cereals and Bars',
               'Butter & Margarine',
               'Cereals and Granolas',
               'Cheese Varieties',
               'Dairy Processing Products',
               'Eggs and Egg Products',
               'Fresh Dairy Products',
               'Butter & Ghee',
               'Condensed Milk',
               'Free-Range Eggs',
               'Organic Honey'],
  'menu_image': 'boiled-egg.svg'},
 {'name': 'Breads & Bakery',
  'slug': 'bakery',
  'children': ['Bakery Pastries and Rolls',
               'Fresh Bread Varieties',
               'Glazed and Filled Products',
               'Gluten-Free Alternatives',
               'Organic and Natural Breads',
               'Pizza and Flatbreads',
               'Sandwich Bread and Wraps',
               'Sweets and Pastry Products',
               'Artisan Sourdough',
               'Buns & Rolls',
               'Stoneground Atta',
               'Flatbreads & Rotis'],
  'menu_image': 'toast-bread.svg'},
 {'name': 'Beverages',
  'slug': 'beverages',
  'children': ['Drink Boxes & Pouches',
               'Coffee',
               'Craft Beer',
               'Milk & Plant-Based Milk',
               'Soda & Pop',
               'Sparkling Water',
               'Himalayan Green Tea',
               'Cold-Pressed Juices',
               'Plant-Based Milk',
               'Artisan Coffee'],
  'menu_image': 'cup.svg'},
 {'name': 'Frozen Foods',
  'slug': 'frozen',
  'children': ['Frozen Veggies', 'Himalayan Momos', 'Frozen Entrees'],
  'menu_image': 'snowflake.svg'},
 {'name': 'Biscuits & Snacks',
  'slug': 'snacks',
  'children': ['Chips & Pretzels', 'Crackers & Biscuits', 'Roasted Himalayan Nuts'],
  'menu_image': 'bar.svg'},
 {'name': 'Grocery & Staples', 'slug': 'grocery', 'children': ['Spices & Seasonings', 'Organic Staples', 'Oils & Ghee'], 'menu_image': 'wheat.svg'},
 {'name': 'Household Needs', 'slug': 'household', 'children': [], 'menu_image': 'scoop.svg'},
 {'name': 'Healthcare', 'slug': 'healthcare', 'children': [], 'menu_image': 'toilet-paper.svg'},
 {'name': 'Baby & Pregnancy', 'slug': 'baby', 'children': [], 'menu_image': 'baby-boy.svg'}]


def seed(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Subcategory = apps.get_model('catalog', 'Subcategory')
    db = schema_editor.connection.alias
    for position, row in enumerate(ROWS):
        category = Category.objects.using(db).filter(slug=row['slug']).first()
        if category is None:
            category = Category.objects.using(db).filter(name__iexact=row['name']).first()
        if category is None:
            category = Category.objects.using(db).create(
                name=row['name'], slug=row['slug'], legacy_key=row['slug'],
                position=position, menu_image=row['menu_image'],
            )
        elif not category.legacy_key:
            # Preserve existing admin choices, names, status and icon.
            category.legacy_key = row['slug']
            category.save(using=db, update_fields=['legacy_key'])
        for order, name in enumerate(row['children']):
            slug = slugify(name, allow_unicode=True)
            existing = Subcategory.objects.using(db).filter(category=category)
            if existing.filter(name__iexact=name).exists() or existing.filter(slug=slug).exists():
                continue
            Subcategory.objects.using(db).create(category=category, name=name, slug=slug, position=order)


class Migration(migrations.Migration):
    dependencies = [('catalog', '0002_category_legacy_key_category_menu_image')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
