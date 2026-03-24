import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment, Booking
from .serializers import (
    PaymentSerializer, 
    BookingSerializer, 
    MpesaCallbackSerializer,
    PaymentStatusUpdateSerializer
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """
    Handle M-Pesa payment callbacks from Daraja API
    
    Expected payload format:
    {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "...",
                "CheckoutRequestID": "...",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 100},
                        {"Name": "MpesaReceiptNumber", "Value": "..."},
                        {"Name": "PhoneNumber", "Value": "..."},
                        {"Name": "TransactionDate", "Value": "..."}
                    ]
                }
            }
        }
    }
    """
    try:
        # Parse and validate callback data
        serializer = MpesaCallbackSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid callback data: {serializer.errors}")
            return Response(
                {"error": "Invalid callback data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        callback_data = serializer.validated_data['Body']
        stk_callback = callback_data['stkCallback']
        
        checkout_request_id = stk_callback['CheckoutRequestID']
        merchant_request_id = stk_callback.get('MerchantRequestID')
        result_code = stk_callback.get('ResultCode', 1)
        result_description = stk_callback.get('ResultDesc', 'Unknown error')
        
        logger.info(f"M-Pesa callback for CheckoutRequestID: {checkout_request_id}")
        
        # Find the payment record
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update payment status based on result
        with transaction.atomic():
            if result_code == 0:  # Success
                payment.mark_completed(result_code, result_description, callback_data)
                
                # Update associated booking if exists
                try:
                    booking = Booking.objects.filter(payment=payment).first()
                    if booking:
                        booking.mark_paid()
                        logger.info(f"Booking {booking.booking_id} marked as paid")
                except Exception as e:
                    logger.error(f"Error updating booking: {e}")
                
                logger.info(f"Payment {checkout_request_id} completed successfully")
                
            else:  # Failed
                payment.mark_failed(result_code, result_description, callback_data)
                logger.info(f"Payment {checkout_request_id} failed: {result_description}")
        
        # Return success response to M-Pesa
        return Response({
            "status": "success",
            "message": "Callback processed successfully",
            "checkout_request_id": checkout_request_id
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        return Response(
            {"error": "Internal server error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PaymentListView(APIView):
    """API view to list all payments"""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get all payment records"""
        payments = Payment.objects.all()
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new payment record (for testing)"""
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentDetailView(APIView):
    """API view to get payment details"""
    
    permission_classes = [AllowAny]
    
    def get(self, request, checkout_request_id):
        """Get payment details by checkout request ID"""
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
            serializer = PaymentSerializer(payment)
            return Response(serializer.data)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class BookingListView(APIView):
    """API view to list all bookings"""
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get all booking records"""
        bookings = Booking.objects.all()
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


class BookingDetailView(APIView):
    """API view to get booking details"""
    
    permission_classes = [AllowAny]
    
    def get(self, request, booking_id):
        """Get booking details by booking ID"""
        try:
            booking = Booking.objects.get(booking_id=booking_id)
            serializer = BookingSerializer(booking)
            return Response(serializer.data)
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )


@api_view(['POST'])
@permission_classes([AllowAny])
def update_payment_status(request):
    """
    Manual endpoint to update payment status (for testing)
    """
    serializer = PaymentStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    checkout_request_id = serializer.validated_data['checkout_request_id']
    payment_status = serializer.validated_data['status']
    result_code = serializer.validated_data['result_code']
    result_description = serializer.validated_data['result_description']
    callback_data = serializer.validated_data.get('callback_data', {})
    
    try:
        payment = Payment.objects.get(checkout_request_id=checkout_request_id)
        
        with transaction.atomic():
            if payment_status == 'completed':
                payment.mark_completed(result_code, result_description, callback_data)
                
                # Update associated booking
                booking = Booking.objects.filter(payment=payment).first()
                if booking:
                    booking.mark_paid()
                    
            elif payment_status == 'failed':
                payment.mark_failed(result_code, result_description, callback_data)
        
        return Response({
            "status": "success",
            "message": f"Payment {checkout_request_id} updated to {payment_status}"
        })
        
    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
        "service": "M-Pesa Django Callback Service"
    })
