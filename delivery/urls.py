from django.urls import path
from .views import settings_view

app_name = 'delivery'
urlpatterns = [path('', settings_view, name='settings')]
