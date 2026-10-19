from django.urls import path
from . import views

app_name = 'catalog'
urlpatterns = [path('', views.index, name='index')]
for kind in ('category', 'subcategory'):
    urlpatterns += [
        path(f'{kind}/new/', views.edit, {'kind': kind}, name=f'{kind}-add'),
        path(f'{kind}/<int:pk>/edit/', views.edit, {'kind': kind}, name=f'{kind}-edit'),
        path(f'{kind}/<int:pk>/status/', views.status, {'kind': kind}, name=f'{kind}-status'),
        path(f'{kind}/<int:pk>/delete/', views.delete, {'kind': kind}, name=f'{kind}-delete'),
    ]
