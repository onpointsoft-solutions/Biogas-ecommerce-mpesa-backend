from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def root_view(request):
    return JsonResponse({
        "message": "Biogas E-commerce M-Pesa Backend API",
        "version": "1.0.0",
        "endpoints": {
            "api": "/api/",
            "health": "/api/health/",
            "mpesa": "/api/mpesa/",
            "payments": "/api/payments/",
            "bookings": "/api/bookings/"
        }
    })

urlpatterns = [
    path('', root_view, name='root'),
    path('admin/', admin.site.urls),
    path('api/', include('payments.urls')),
]
