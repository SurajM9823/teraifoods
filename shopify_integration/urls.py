from django.urls import path
from .webhooks import receive

app_name = 'shopify_integration'
urlpatterns = [path('webhook/', receive, name='webhook')]
