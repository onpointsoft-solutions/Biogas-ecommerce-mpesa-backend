from django.urls import path
from . import mpesa_views

urlpatterns = [
    # M-Pesa payment endpoints
    path('mpesa/initiate/', mpesa_views.initiate_mpesa_payment, name='initiate_mpesa_payment'),
    path('mpesa/status/', mpesa_views.check_payment_status, name='check_payment_status'),
    path('mpesa/callback/', mpesa_views.mpesa_callback, name='mpesa_callback'),
    
    # Payment management endpoints
    path('payments/', mpesa_views.payment_list, name='payment_list'),
    path('payments/<str:checkout_request_id>/', mpesa_views.payment_detail, name='payment_detail'),
    
    # Booking management endpoints
    path('bookings/', mpesa_views.booking_list, name='booking_list'),
    path('bookings/<str:booking_id>/', mpesa_views.booking_detail, name='booking_detail'),
    
    # Health check
    path('health/', mpesa_views.health_check, name='health_check'),
]
