from django.db import models
from django.db.models.functions import Lower
from .icons import ICON_CHOICES


class CategoryFields(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, allow_unicode=True, help_text='Stable identifier. Generated from the name when left blank.')
    description = models.TextField(max_length=500, blank=True)
    icon = models.CharField(max_length=64, blank=True, choices=ICON_CHOICES)
    is_active = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0, help_text='Smaller numbers appear first.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('position', 'name', 'pk')

    def __str__(self):
        return self.name


class Category(CategoryFields):
    legacy_key = models.CharField(max_length=40, blank=True, editable=False)
    menu_image = models.CharField(max_length=40, blank=True, choices=[
        (name + '.svg', label) for name, label in (
            ('apple', 'Fruit'), ('meat', 'Meat'), ('boiled-egg', 'Breakfast'),
            ('toast-bread', 'Bread'), ('cup', 'Drinks'), ('snowflake', 'Frozen'),
            ('bar', 'Snacks'), ('wheat', 'Grocery'), ('scoop', 'Household'),
            ('toilet-paper', 'Healthcare'), ('baby-boy', 'Baby'),
        )
    ], help_text='Original storefront artwork. A selected Font Awesome icon takes priority.')
    class Meta(CategoryFields.Meta):
        abstract = False
        verbose_name_plural = 'categories'
        constraints = [
            models.UniqueConstraint(Lower('name'), name='catalog_category_name_ci'),
            models.UniqueConstraint(fields=['slug'], name='catalog_category_slug_unique'),
        ]


class Subcategory(CategoryFields):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='subcategories')

    class Meta(CategoryFields.Meta):
        abstract = False
        verbose_name_plural = 'subcategories'
        constraints = [
            models.UniqueConstraint(Lower('name'), 'category', name='catalog_subcategory_name_ci'),
            models.UniqueConstraint(fields=['category', 'slug'], name='catalog_subcategory_slug_unique'),
        ]

    @property
    def effective_active(self):
        return self.is_active and self.category.is_active
