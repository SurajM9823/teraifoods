from django.urls import path
from . import views

app_name = 'cms'
urlpatterns = [
    # Homepage carousel & 4 information blocks
    path('', views.dashboard, name='dashboard'),
    path('banners/new/', views.edit, {'kind': 'banner'}, name='banner-add'),
    path('banners/<int:pk>/', views.edit, {'kind': 'banner'}, name='banner-edit'),
    path('banners/<int:pk>/delete/', views.delete_banner, name='banner-delete'),
    path('information/<int:pk>/', views.edit, {'kind': 'information'}, name='information-edit'),

    # Contact Settings & Social Links
    path('contact-settings/', views.contact_settings, name='contact-settings'),

    # FAQs
    path('faqs/', views.faqs_index, name='faqs-index'),
    path('faqs/add/', views.faq_edit, name='faq-add'),
    path('faqs/<int:pk>/', views.faq_edit, name='faq-edit'),
    path('faqs/<int:pk>/delete/', views.faq_delete, name='faq-delete'),

    # Map Hubs
    path('hubs/', views.hubs_index, name='hubs-index'),
    path('hubs/add/', views.hub_edit, name='hub-add'),
    path('hubs/<int:pk>/', views.hub_edit, name='hub-edit'),
    path('hubs/<int:pk>/delete/', views.hub_delete, name='hub-delete'),

    # Customer Support Enquiries
    path('inquiries/', views.inquiries_index, name='inquiries-index'),
    path('inquiries/<int:pk>/', views.inquiry_detail, name='inquiry-detail'),
]
