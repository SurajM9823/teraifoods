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


from .models import ContactSettings, FAQItem, ContactInquiry, ContactHub

@admin.register(ContactSettings)
class ContactSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not ContactSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(FAQItem)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('question', 'answer')

@admin.register(ContactHub)
class ContactHubAdmin(admin.ModelAdmin):
    list_display = ('name', 'tag', 'order', 'is_active')
    list_editable = ('order', 'is_active')

@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'topic_display', 'status', 'created_at')
    list_filter = ('status', 'topic')
    search_fields = ('name', 'email', 'message')
    readonly_fields = ('name', 'email', 'phone', 'topic', 'message', 'ip_address', 'created_at', 'updated_at')
    fields = readonly_fields + ('status', 'admin_notes')

    def has_add_permission(self, request):
        return False
