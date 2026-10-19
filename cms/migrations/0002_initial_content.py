from django.db import migrations


def seed(apps, schema_editor):
    Banner = apps.get_model('cms', 'Banner')
    Information = apps.get_model('cms', 'InformationBlock')
    alias = schema_editor.connection.alias
    for position, title in enumerate((
        'Get the best quality products at the lowest prices',
        'Explore our world of grocery products',
    )):
        Banner.objects.using(alias).create(
            title=title, badge='Discover Terai Foods',
            description='Explore our grocery range and find your everyday favourites.',
            fallback_image=f'slider-0{position + 1}.jpg', position=position,
            button_label='Shop Now', destination='/shop/',
        )
    for slot, title, description in (
        (1, 'Payment information', 'Find payment information before placing your order.'),
        (2, 'New stocks and offers', 'Explore our grocery range for new arrivals and available offers.'),
        (3, 'Product information', 'Check product details to find the right groceries for your needs.'),
        (4, 'Delivery information', 'Contact our team for delivery availability and timings.'),
    ):
        Information.objects.using(alias).create(slot=slot, title=title, description=description)


class Migration(migrations.Migration):
    dependencies = [('cms', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
