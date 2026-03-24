from django.db import models
from django.utils import timezone


class Payment(models.Model):
    """M-Pesa payment model"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Payment details
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Transaction details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    reference = models.CharField(max_length=100, blank=True)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    callback_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.checkout_request_id} - {self.status}"
    
    def mark_completed(self, result_code, result_description, callback_data):
        """Mark payment as completed"""
        self.status = 'completed'
        self.result_code = result_code
        self.result_description = result_description
        self.callback_data = callback_data
        self.completed_at = timezone.now()
        self.save()
    
    def mark_failed(self, result_code, result_description, callback_data):
        """Mark payment as failed"""
        self.status = 'failed'
        self.result_code = result_code
        self.result_description = result_description
        self.callback_data = callback_data
        self.save()


class Booking(models.Model):
    """Booking model for service payments"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Booking details
    booking_id = models.CharField(max_length=100, unique=True)
    customer_id = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=200)
    service_name = models.CharField(max_length=200)
    technician_id = models.CharField(max_length=100, blank=True, null=True)
    technician_name = models.CharField(max_length=200, blank=True, null=True)
    technician_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Pricing
    service_fee = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status and timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    booking_date = models.DateTimeField()
    service_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Address and details
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
    
    # Link to payment
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['customer_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_id} - {self.service_name}"
    
    def mark_paid(self):
        """Mark booking as paid"""
        self.status = 'paid'
        self.save()
