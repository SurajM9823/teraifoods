from django.urls import path
from . import product_views as views

app_name = 'products'
urlpatterns = [
    path('', views.index, name='index'),
    path('add/', views.edit, name='add'),
    path('<int:pk>/', views.edit, name='edit'),
    path('<int:pk>/stock/', views.stock, name='stock'),
    path('<int:pk>/images/', views.images, name='images'),
]
