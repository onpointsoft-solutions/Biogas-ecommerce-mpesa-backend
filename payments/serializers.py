from rest_framework import serializers
from .models import Payment, Booking


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    class Meta:
        model = Payment
        fields = [
            'id', 'checkout_request_id', 'merchant_request_id',
            'amount', 'phone_number', 'reference', 'status',
            'result_code', 'result_description', 'created_at',
            'updated_at', 'completed_at', 'metadata', 'callback_data'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']


class BookingSerializer(serializers.ModelSerializer):
    """Serializer for Booking model"""
    payment_details = PaymentSerializer(source='payment', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_id', 'customer_id', 'customer_name',
            'service_name', 'technician_id', 'service_fee',
            'platform_fee', 'total_amount', 'status',
            'booking_date', 'service_date', 'created_at',
            'updated_at', 'address', 'description', 'payment_details'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MpesaCallbackSerializer(serializers.Serializer):
    """Serializer for M-Pesa callback data"""
    
    Body = serializers.JSONField()
    
    def validate_Body(self, value):
        """Validate the callback body structure"""
        if 'stkCallback' not in value:
            raise serializers.ValidationError("Invalid M-Pesa callback structure")
        
        stk_callback = value['stkCallback']
        
        if 'MerchantRequestID' not in stk_callback or 'CheckoutRequestID' not in stk_callback:
            raise serializers.ValidationError("Missing required M-Pesa callback fields")
        
        return value


class PaymentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating payment status"""
    
    checkout_request_id = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=['completed', 'failed'])
    result_code = serializers.IntegerField()
    result_description = serializers.CharField()
    callback_data = serializers.JSONField(required=False)
