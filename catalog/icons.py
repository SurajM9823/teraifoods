"""Free icons bundled with the site; no external scripts or arbitrary HTML."""
ICON_CHOICES = [('', 'No icon')] + [
    (f'fa-solid fa-{name}', label) for name, label in (
        ('basket-shopping', 'Shopping basket'), ('store', 'Store'),
        ('apple-whole', 'Fruit'), ('carrot', 'Vegetables'), ('leaf', 'Leaf / organic'),
        ('seedling', 'Seedling'), ('wheat-awn', 'Grains'), ('bowl-rice', 'Rice'),
        ('bread-slice', 'Bread'), ('cookie-bite', 'Biscuits'), ('cheese', 'Dairy'),
        ('egg', 'Eggs'), ('fish', 'Fish'), ('drumstick-bite', 'Meat'),
        ('pepper-hot', 'Spices'), ('mug-hot', 'Tea / coffee'),
        ('bottle-water', 'Water'), ('wine-bottle', 'Bottled drinks'),
        ('ice-cream', 'Ice cream'), ('snowflake', 'Frozen food'),
        ('jar', 'Jar / preserves'), ('candy-cane', 'Sweets'),
        ('pump-soap', 'Cleaning'), ('spray-can-sparkles', 'Household'),
        ('heart', 'Health'), ('baby', 'Baby'), ('paw', 'Pets'),
        ('box', 'Box / bulk'), ('tags', 'Offers'), ('utensils', 'Food'),
    )
]
