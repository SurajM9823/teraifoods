from django.urls import path
from . import views

app_name = 'orders'
urlpatterns = [
    path('checkout/',views.checkout,name='checkout'),
    path('access/',views.access),
    path('history/',views.history),
    path('webhook/stripe/',views.webhook),
    path('addresses/',views.addresses),
    path('addresses/<int:pk>/',views.addresses),
    path('reviews/<int:product_id>/',views.reviews),
    path('notifications/',views.notifications),
    path('admin/reviews/<int:pk>/',views.moderate_review),
    path('review/<int:pk>/action/',views.review_action),
    path('<uuid:public_id>/',views.detail),
    path('<uuid:public_id>/action/',views.action),
    path('<uuid:public_id>/admin/',views.admin_action),
    path('<uuid:public_id>/handover/',views.driver_handover),
]
