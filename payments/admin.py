from django.contrib import admin
from .models import Payment, Booking


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'checkout_request_id', 'amount', 'phone_number', 
        'status', 'result_code', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'result_code', 'created_at']
    search_fields = ['checkout_request_id', 'phone_number', 'reference']
    readonly_fields = [
        'checkout_request_id', 'merchant_request_id', 'created_at', 
        'updated_at', 'completed_at', 'callback_data'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('checkout_request_id', 'merchant_request_id', 'amount', 'phone_number', 'reference')
        }),
        ('Status', {
            'fields': ('status', 'result_code', 'result_description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('metadata', 'callback_data'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_id', 'customer_name', 'service_name', 
        'total_amount', 'status', 'booking_date', 'service_date'
    ]
    list_filter = ['status', 'booking_date', 'service_date']
    search_fields = ['booking_id', 'customer_name', 'customer_id', 'service_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('booking_id', 'customer_id', 'customer_name', 'service_name', 'technician_id')
        }),
        ('Pricing', {
            'fields': ('service_fee', 'platform_fee', 'total_amount')
        }),
        ('Status & Dates', {
            'fields': ('status', 'booking_date', 'service_date')
        }),
        ('Details', {
            'fields': ('address', 'description')
        }),
        ('Payment', {
            'fields': ('payment',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
