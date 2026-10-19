from django.contrib import admin
from .forms import BannerForm
from .models import Banner, InformationBlock


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    form = BannerForm
    list_display = ('title', 'position', 'is_active', 'updated_at')
    list_filter = ('is_active',)


@admin.register(InformationBlock)
class InformationAdmin(admin.ModelAdmin):
    list_display = ('slot', 'title', 'is_active')
