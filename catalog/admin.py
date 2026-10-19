from django.contrib import admin
from .forms import CategoryForm, SubcategoryForm
from .models import Category, Subcategory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
    list_display = ('name', 'slug', 'is_active', 'position')
    search_fields = ('name', 'slug')
    list_filter = ('is_active',)


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    form = SubcategoryForm
    list_display = ('name', 'category', 'is_active', 'position')
    list_select_related = ('category',)
    search_fields = ('name', 'slug', 'category__name')
    list_filter = ('category', 'is_active')
