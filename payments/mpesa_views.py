import os
import base64
import json
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import requests

from .models import Payment, Booking
from .serializers import (
    PaymentSerializer, 
    BookingSerializer, 
    MpesaCallbackSerializer,
    PaymentStatusUpdateSerializer
)

logger = logging.getLogger(__name__)

# Daraja Configuration (Sandbox - move to environment variables in production)
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY', 'YourConsumerKeyHere')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET', 'YourConsumerSecretHere')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY', 'bfb279c9a6ffbdf4f8b4c3e8e3c7b3c8e3c7b3c8e3c7b3c8e3c7b3c8e3c7b3c')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE', '174379')
MPESA_BASE_URL = 'https://sandbox.safaricom.co.ke'
MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://your-domain.com/api/mpesa/callback/')

# Cache for OAuth token
_oauth_token = None
_token_expiry = None

def get_oauth_token():
    """Get OAuth token from Daraja API with caching"""
    global _oauth_token, _token_expiry
    
    # Check if token is still valid
    if _oauth_token and _token_expiry and datetime.now().timestamp() < _token_expiry:
        return _oauth_token
    
    try:
        # Create credentials
        credentials = base64.b64encode(f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}".encode()).decode()
        
        # Request OAuth token
        headers = {'Authorization': f'Basic {credentials}'}
        response = requests.get(
            f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            _oauth_token = data['access_token']
            _token_expiry = datetime.now().timestamp() + 3599  # Token expires in 1 hour
            logger.info("OAuth token obtained successfully")
            return _oauth_token
        else:
            logger.error(f"OAuth token request failed: {response.status_code} - {response.text}")
            raise Exception(f"Failed to get OAuth token: {response.status_code}")
            
    except Exception as e:
        logger.error(f"OAuth token error: {str(e)}")
        raise Exception(f"OAuth token error: {str(e)}")

def generate_stk_push_password(timestamp):
    """Generate STK Push password"""
    data = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(data.encode()).decode()

def format_phone_number(phone):
    """Format phone number for M-Pesa"""
    cleaned = ''.join(filter(str.isdigit, str(phone)))
    
    if cleaned.startswith('0'):
        return '254' + cleaned[1:]
    elif cleaned.startswith('7'):
        return '254' + cleaned
    elif not cleaned.startswith('254'):
        return '254' + cleaned
    
    return cleaned

@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([AllowAny])
def initiate_mpesa_payment(request):
    """
    Initiate M-Pesa STK Push payment
    Expected payload:
    {
        "booking_id": "BK123",
        "customer_id": "CUST123", 
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "customer_phone": "+254712345678",
        "service_name": "Gas Installation",
        "amount": 1500.00,
        "service_fee": 1200.00,
        "platform_fee": 300.00
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['booking_id', 'customer_phone', 'amount', 'customer_name', 'customer_email']
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {"error": f"Missing required field: {field}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Format phone number
        phone_number = format_phone_number(data['customer_phone'])
        amount = float(data['amount'])
        
        # Create payment record
        payment = Payment.objects.create(
            amount=amount,
            phone_number=phone_number,
            reference=data['booking_id'],
            status='pending',
            metadata={
                'booking_id': data['booking_id'],
                'customer_id': data.get('customer_id', ''),
                'customer_name': data['customer_name'],
                'customer_email': data['customer_email'],
                'service_name': data.get('service_name', ''),
                'service_fee': data.get('service_fee', 0),
                'platform_fee': data.get('platform_fee', 0),
                'technician_id': data.get('technician_id', ''),
                'technician_name': data.get('technician_name', ''),
                'technician_phone': data.get('technician_phone', ''),
            }
        )
        
        # Get OAuth token
        try:
            access_token = get_oauth_token()
        except Exception as e:
            payment.mark_failed(1, f'OAuth error: {str(e)}', {})
            return Response(
                {"error": "Authentication failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Generate timestamp and password
        timestamp = str(int(datetime.now().timestamp() * 1000))
        password = generate_stk_push_password(timestamp)
        
        # Prepare STK Push request
        stk_push_data = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": MPESA_CALLBACK_URL,
            "AccountReference": data['booking_id'],
            "TransactionDesc": f"Payment for {data.get('service_name', 'service')}"
        }
        
        # Send STK Push request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            headers=headers,
            json=stk_push_data
        )
        
        if response.status_code == 200:
            stk_response = response.json()
            
            if stk_response.get('ResponseCode') == '0':
                # Update payment with STK Push details
                payment.checkout_request_id = stk_response.get('CheckoutRequestID')
                payment.merchant_request_id = stk_response.get('MerchantRequestID')
                payment.save()
                
                logger.info(f"STK Push sent successfully: {payment.checkout_request_id}")
                
                return Response({
                    "status": "success",
                    "message": "STK Push sent successfully",
                    "checkout_request_id": payment.checkout_request_id,
                    "merchant_request_id": payment.merchant_request_id,
                    "payment_id": payment.id
                }, status=status.HTTP_200_OK)
            else:
                # STK Push failed
                error_msg = stk_response.get('errorMessage', 'STK Push failed')
                payment.mark_failed(stk_response.get('ResponseCode', '1'), error_msg, stk_response)
                
                return Response(
                    {"error": "STK Push failed", "details": error_msg},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # HTTP request failed
            error_msg = f"HTTP {response.status_code}: {response.text}"
            payment.mark_failed(response.status_code, error_msg, {})
            
            return Response(
                {"error": "STK Push request failed", "details": error_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Payment initiation error: {str(e)}")
        return Response(
            {"error": "Payment initiation failed", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([AllowAny])
def check_payment_status(request):
    """
    Check payment status by checkout request ID
    Expected payload:
    {
        "checkout_request_id": "ws_CO_123456789"
    }
    """
    try:
        data = request.data
        checkout_request_id = data.get('checkout_request_id')
        
        if not checkout_request_id:
            return Response(
                {"error": "checkout_request_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find payment
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # If payment is already completed, return current status
        if payment.status in ['completed', 'failed']:
            return Response({
                "status": payment.status,
                "payment": PaymentSerializer(payment).data
            })
        
        # Query payment status from Daraja
        try:
            access_token = get_oauth_token()
        except Exception as e:
            return Response(
                {"error": "Authentication failed", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        timestamp = str(int(datetime.now().timestamp() * 1000))
        password = generate_stk_push_password(timestamp)
        
        query_data = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            headers=headers,
            json=query_data
        )
        
        if response.status_code == 200:
            query_response = response.json()
            
            if query_response.get('ResponseCode') == '0':
                # Payment successful
                callback_metadata = query_response.get('CallbackMetadata', {})
                payment.mark_completed(
                    query_response.get('ResultCode', 0),
                    query_response.get('ResultDesc', 'Success'),
                    query_response
                )
                
                # Update associated booking
                booking = Booking.objects.filter(booking_id=payment.reference).first()
                if booking:
                    booking.mark_paid()
                    booking.payment = payment
                    booking.save()
                
            else:
                # Payment failed
                payment.mark_failed(
                    query_response.get('ResultCode', 1),
                    query_response.get('ResultDesc', 'Payment failed'),
                    query_response
                )
            
            return Response({
                "status": payment.status,
                "payment": PaymentSerializer(payment).data
            })
            
        else:
            return Response(
                {"error": "Status check failed", "details": f"HTTP {response.status_code}: {response.text}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Payment status check error: {str(e)}")
        return Response(
            {"error": "Status check failed", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@csrf_exempt
@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([AllowAny])
def mpesa_callback(request):
    """
    Handle M-Pesa payment callbacks from Daraja API
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
                    booking = Booking.objects.filter(booking_id=payment.reference).first()
                    if booking:
                        booking.mark_paid()
                        booking.payment = payment
                        booking.save()
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

# Keep existing views for payment management
@api_view(['GET'])
@permission_classes([AllowAny])
def payment_list(request):
    """Get all payment records"""
    payments = Payment.objects.all()
    serializer = PaymentSerializer(payments, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def payment_detail(request, checkout_request_id):
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

@api_view(['GET'])
@permission_classes([AllowAny])
def booking_detail(request, booking_id):
    """Get booking details with technician information"""
    try:
        booking = Booking.objects.get(booking_id=booking_id)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
    except Booking.DoesNotExist:
        return Response(
            {"error": "Booking not found"},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def booking_list(request):
    """Get all booking records"""
    bookings = Booking.objects.all()
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        "status": "healthy",
        "timestamp": timezone.now().isoformat(),
        "service": "M-Pesa Django Backend Service",
        "mpesa_configured": bool(MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET and MPESA_PASSKEY)
    })
