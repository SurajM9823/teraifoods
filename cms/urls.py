from django.urls import path
from . import views

app_name = 'cms'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('banners/new/', views.edit, {'kind': 'banner'}, name='banner-add'),
    path('banners/<int:pk>/', views.edit, {'kind': 'banner'}, name='banner-edit'),
    path('banners/<int:pk>/delete/', views.delete_banner, name='banner-delete'),
    path('information/<int:pk>/', views.edit, {'kind': 'information'}, name='information-edit'),
]
