# Views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from .serializers import RegisterSerializer, LoginSerializer


class RegisterView(APIView):
    """
    Register a new user (shop owner or customer) and return auth token
    """
    permission_classes = []           # anyone can register
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            profile = user.userprofile  # from OneToOne

            return Response({
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": profile.role,
                    "contact_info": profile.contact_info
                },
                "message": "Account created successfully."
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Login and return auth token
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token, _ = Token.objects.get_or_create(user=user)

            profile = user.userprofile

            return Response({
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": profile.role,
                    "contact_info": profile.contact_info
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Product, UserProfile
from .serializers import ProductCreateSerializer


class AddProductView(APIView):
    """
    POST /api/products/add/
    Only authenticated users with role='owner' can add products
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if user has owner role
        try:
            profile = request.user.userprofile
            if profile.role != 'owner':
                return Response(
                    {"detail": "Only shop owners can add products."},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProfile.DoesNotExist:
            return Response(
                {"detail": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProductCreateSerializer(data=request.data)

        if serializer.is_valid():
            # Automatically assign the current owner
            product = serializer.save(owner=profile)

            return Response(
                {
                    "message": "Product added successfully",
                    "product": ProductCreateSerializer(product).data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework import generics
from rest_framework.permissions import AllowAny   # or IsAuthenticated if you want only logged-in users
from .models import Product
from .serializers import ProductSerializer


class ProductListView(generics.ListAPIView):
    """
    GET /api/products/
    Returns list of all products (public or filtered later)
    """
    queryset = Product.objects.filter(is_available=True)
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]  # change to IsAuthenticated if needed


from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Cart, CartItem, Product, UserProfile
from .serializers import CartSerializer, CartItemSerializer


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            profile = request.user.userprofile
            if profile.role != 'customer':
                return Response({"detail": "Only customers can add to cart"}, status=403)
        except UserProfile.DoesNotExist:
            return Response({"detail": "Profile not found"}, status=400)

        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)

        if not product_id:
            return Response({"detail": "product_id is required"}, status=400)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found"}, status=404)

        # Get or create cart
        cart, created = Cart.objects.get_or_create(customer=profile)

        # Check if item already in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += int(quantity)
            cart_item.save()

        return Response(
            {"message": "Added to cart", "cart": CartSerializer(cart).data},
            status=status.HTTP_201_CREATED
        )


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            cart = Cart.objects.get(customer=request.user.userprofile)
            return Response(CartSerializer(cart).data)
        except Cart.DoesNotExist:
            return Response({"items": [], "total_items": 0, "total_price": "0.00"})

class RemoveCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            profile = request.user.userprofile
            if profile.role != 'customer':
                return Response({"detail": "Only customers can modify cart"}, status=403)
        except UserProfile.DoesNotExist:
            return Response({"detail": "Profile not found"}, status=400)

        try:
            cart_item = CartItem.objects.get(id=pk, cart__customer=profile)
            cart_item.delete()
            return Response({"message": "Item removed from cart"}, status=status.HTTP_204_NO_CONTENT)
        except CartItem.DoesNotExist:
            return Response({"detail": "Cart item not found or does not belong to you"}, status=404)
        

# core/views.py (add or update)
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from .serializers import ProductSerializer

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission: allow anyone to read (list/retrieve), but only owner to delete/update
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write permissions only for the owner
        return obj.owner == request.user.userprofile

class ProductViewSet(viewsets.ModelViewSet):
    """
    API for products: list all, retrieve, delete (owner only)
    """
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]  # authenticated for write, anyone for read

    def get_queryset(self):
        # Return all products – filter by owner if needed later
        return Product.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        # Set owner automatically on create
        serializer.save(owner=self.request.user.userprofile)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Product deleted successfully"}, status=status.HTTP_204_NO_CONTENT)



# core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import requests
import base64
from datetime import datetime
from .models import Cart, Order, OrderItem

# core/views.py  → replace your CheckoutView with this version
class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def get_access_token(self):
        auth_url = (
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            if settings.MPESA_ENVIRONMENT == 'sandbox'
            else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        )
        auth_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
        auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        headers = {"Authorization": f"Basic {auth}"}
        response = requests.get(auth_url, headers=headers)
        response.raise_for_status()
        return response.json()['access_token']

    def _simulate_successful_payment(self, order):
        """For local testing: mark as paid/completed immediately"""
        order.is_paid = True
        order.status = 'completed'
        order.payment_reference = f"SIM-{order.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        order.save(update_fields=['is_paid', 'status', 'payment_reference'])

        # Reduce stock (important!)
        for item in order.items.select_related('product'):
            try:
                item.product.reduce_stock(item.quantity)
            except ValueError as e:
                # In real app → log / notify admin / mark order issue
                print(f"Stock warning (sim): {e}")

        # Clear cart
        Cart.objects.filter(customer=order.customer).delete()

    def post(self, request):
        raw_phone = request.data.get('phone', '').strip()
        if not raw_phone:
            return Response({'error': 'Phone number is required'}, status=400)

        # Phone normalization (your existing logic – kept as-is)
        phone_number = raw_phone
        if phone_number.startswith('0') and len(phone_number) == 10 and phone_number[1].isdigit():
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif not (phone_number.startswith('254') and len(phone_number) == 12):
            return Response(
                {'error': 'Invalid phone number format. Use 2547xxxxxxxx or 07xxxxxxxx'},
                status=400
            )

        if not (phone_number.startswith('254') and len(phone_number) == 12 and phone_number[3:].isdigit()):
            return Response({'error': 'Invalid phone after normalization'}, status=400)

        try:
            profile = request.user.userprofile
            cart = Cart.objects.get(customer=profile)

            if not cart.items.exists():
                return Response({'error': 'Your cart is empty'}, status=400)

            total_amount = sum(
                item.product.price * item.quantity for item in cart.items.all()
            )

            if total_amount <= 0:
                return Response({'error': 'Invalid order amount'}, status=400)

            # Create order
            order = Order.objects.create(
                customer=profile,
                total_amount=total_amount,
                is_paid=False,
                status='pending'
            )

            # Copy items
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_purchase=item.product.price
                )

            # ────────────────────────────────────────
            #  Simulation mode (for local/test)
            # ────────────────────────────────────────
            if getattr(settings, 'MPESA_SIMULATE_SUCCESS', False):
                self._simulate_successful_payment(order)
                return Response({
                    'success': True,
                    'message': 'TEST MODE: Payment simulated successfully. Order completed.',
                    'order_id': order.id,
                    'simulated': True,
                    'payment_reference': order.payment_reference
                }, status=200)

            # ────────────────────────────────────────
            # Real Daraja STK Push
            # ────────────────────────────────────────
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password_str = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
            password = base64.b64encode(password_str.encode('utf-8')).decode('utf-8')

            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": str(int(total_amount)),
                "PartyA": phone_number,
                "PartyB": settings.MPESA_SHORTCODE,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": f"Order-{order.id}",
                "TransactionDesc": f"Payment for order #{order.id}"
            }

            stk_url = (
                "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
                if settings.MPESA_ENVIRONMENT == 'sandbox'
                else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            )

            headers = {
                "Authorization": f"Bearer {self.get_access_token()}",
                "Content-Type": "application/json"
            }

            response = requests.post(stk_url, json=payload, headers=headers)

            if response.status_code != 200:
                order.delete()
                return Response({
                    'success': False,
                    'error': 'Failed to connect to M-Pesa',
                    'status': response.status_code,
                    'detail': response.text
                }, status=response.status_code)

            resp_data = response.json()

            if resp_data.get('ResponseCode') == '0':
                # Real mode: just confirm STK sent
                return Response({
                    'success': True,
                    'message': 'Payment request sent! Check your phone for STK prompt.',
                    'order_id': order.id,
                    'checkout_request_id': resp_data.get('CheckoutRequestID'),
                    'merchant_request_id': resp_data.get('MerchantRequestID')
                }, status=200)
            else:
                order.delete()
                return Response({
                    'success': False,
                    'error': resp_data.get('ResponseDescription', 'Daraja rejected request'),
                    'daraja_response': resp_data
                }, status=400)

        except Cart.DoesNotExist:
            return Response({'error': 'Cart not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            if 'order' in locals():
                order.delete()
            return Response({'error': f'Server error: {str(e)}'}, status=500)
        

class MpesaCallback(APIView):
    permission_classes = []  # public endpoint – Safaricom calls it

    def post(self, request):
        try:
            body = request.data
            callback = body.get('Body', {}).get('stkCallback', {})
            result_code = callback.get('ResultCode')

            if result_code == 0:
                metadata = callback.get('CallbackMetadata', {}).get('Item', [])
                receipt = next(
                    (item['Value'] for item in metadata if item['Name'] == 'MpesaReceiptNumber'),
                    None
                )

                # Find the most recent unpaid order (improve this later with checkout_request_id)
                order = Order.objects.filter(is_paid=False).order_by('-created_at').first()

                if order:
                    order.is_paid = True
                    order.payment_reference = receipt
                    order.status = 'completed'
                    order.save()

                    # Optional: clear cart
                    Cart.objects.filter(customer=order.customer).delete()

            # Always respond with success to Safaricom (they retry otherwise)
            return Response({
                "ResultCode": 0,
                "ResultDesc": "Accepted"
            })

        except Exception as e:
            return Response({
                "ResultCode": 1,
                "ResultDesc": str(e)
            }, status=500)


# core/views.py
from .serializers import OrderSerializer
# views.py
class CustomerOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        profile = self.request.user.userprofile
        qs = Order.objects.filter(customer=profile, status='pending').order_by('-created_at')
        
        # print(f"[DEBUG] User: {self.request.user.username}")
        # print(f"[DEBUG] Found {qs.count()} orders")
        
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        # print(f"[DEBUG] Serialized data type: {type(serializer.data)}")
        # print(f"[DEBUG] First few items: {serializer.data[:2] if serializer.data else 'empty'}")
        
        return Response(serializer.data)