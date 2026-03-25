import base64
import re
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.db.models import DecimalField, F, Sum
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cart, CartItem, Order, OrderItem, Product, UserProfile
from .serializers import (
    CartSerializer,
    LoginSerializer,
    OrderSerializer,
    OwnerStatsSerializer,
    ProductSerializer,
    RegisterSerializer,
)


class RegisterView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        profile = user.userprofile

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": profile.role,
                    "contact_info": profile.contact_info,
                },
                "message": "Account created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data
        token, _ = Token.objects.get_or_create(user=user)
        profile = user.userprofile

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": profile.role,
                    "contact_info": profile.contact_info,
                },
            }
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        profile = getattr(request.user, "userprofile", None)
        return profile is not None and profile.role == "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        profile = getattr(request.user, "userprofile", None)
        return profile is not None and obj.owner_id == profile.id


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Product.objects.select_related("owner__user").order_by("-created_at")
        if self.request.method in permissions.SAFE_METHODS:
            profile = getattr(self.request.user, "userprofile", None)
            if (
                profile is not None
                and profile.role == "owner"
                and self.request.query_params.get("scope") == "owner"
            ):
                return queryset.filter(owner=profile)
            return queryset.filter(is_available=True, stock_quantity__gt=0)
        return queryset

    def perform_create(self, serializer):
        profile = self.request.user.userprofile
        serializer.save(owner=profile)


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return Response({"detail": "Profile not found"}, status=400)
        if profile.role != "customer":
            return Response({"detail": "Only customers can add to cart"}, status=403)

        product_id = request.data.get("product_id")
        quantity = request.data.get("quantity", 1)

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"detail": "Quantity must be a whole number"}, status=400)

        if quantity < 1:
            return Response({"detail": "Quantity must be at least 1"}, status=400)

        if not product_id:
            return Response({"detail": "product_id is required"}, status=400)

        try:
            product = Product.objects.get(id=product_id, is_available=True, stock_quantity__gt=0)
        except Product.DoesNotExist:
            return Response({"detail": "Product not found"}, status=404)

        cart, _ = Cart.objects.get_or_create(customer=profile)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )

        new_quantity = quantity if created else cart_item.quantity + quantity
        if new_quantity > product.stock_quantity:
            return Response(
                {"detail": f"Only {product.stock_quantity} item(s) available in stock"},
                status=400,
            )

        if not created:
            cart_item.quantity = new_quantity
            cart_item.save(update_fields=["quantity"])

        return Response(
            {"message": "Added to cart", "cart": CartSerializer(cart).data},
            status=status.HTTP_201_CREATED,
        )


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return Response({"detail": "Profile not found"}, status=400)

        cart, _ = Cart.objects.get_or_create(customer=profile)
        return Response(CartSerializer(cart).data)


class CartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_customer_item(self, request, pk):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return None, Response({"detail": "Profile not found"}, status=400)
        if profile.role != "customer":
            return None, Response({"detail": "Only customers can modify cart"}, status=403)

        try:
            return CartItem.objects.select_related("product", "cart").get(
                id=pk,
                cart__customer=profile,
            ), None
        except CartItem.DoesNotExist:
            return None, Response(
                {"detail": "Cart item not found or does not belong to you"},
                status=404,
            )

    def patch(self, request, pk):
        cart_item, error_response = self._get_customer_item(request, pk)
        if error_response:
            return error_response

        quantity = request.data.get("quantity")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"detail": "Quantity must be a whole number"}, status=400)

        if quantity < 1:
            return Response({"detail": "Quantity must be at least 1"}, status=400)
        if quantity > cart_item.product.stock_quantity:
            return Response(
                {"detail": f"Only {cart_item.product.stock_quantity} item(s) available in stock"},
                status=400,
            )

        cart_item.quantity = quantity
        cart_item.save(update_fields=["quantity"])
        return Response({"message": "Cart item updated", "cart": CartSerializer(cart_item.cart).data})

    def delete(self, request, pk):
        cart_item, error_response = self._get_customer_item(request, pk)
        if error_response:
            return error_response

        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    PHONE_PATTERN = re.compile(r"^(?:0[71]\d{8}|\+254[71]\d{8}|254[71]\d{8})$")

    def get_access_token(self):
        auth_url = (
            "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            if settings.MPESA_ENVIRONMENT == "sandbox"
            else "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        )
        auth_string = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
        auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        headers = {"Authorization": f"Basic {auth}"}
        response = requests.get(auth_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()["access_token"]

    def _normalize_phone_number(self, raw_phone):
        phone_number = (raw_phone or "").strip()
        if not phone_number:
            return None
        if not self.PHONE_PATTERN.match(phone_number):
            return None
        if phone_number.startswith("+254"):
            return phone_number[1:]
        if phone_number.startswith("0"):
            return f"254{phone_number[1:]}"
        return phone_number

    def _complete_order(self, order, payment_reference):
        if order.is_paid:
            return

        order.is_paid = True
        order.status = "pending"
        order.payment_reference = payment_reference
        order.save(update_fields=["is_paid", "status", "payment_reference"])

        for item in order.items.select_related("product"):
            if item.product:
                item.product.reduce_stock(item.quantity)

        Cart.objects.filter(customer=order.customer).delete()

    def _simulate_successful_payment(self, order):
        self._complete_order(
            order,
            f"SIM-{order.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        )

    def post(self, request):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return Response({"error": "Profile not found"}, status=400)
        if profile.role != "customer":
            return Response({"error": "Only customers can checkout"}, status=403)

        raw_phone = request.data.get("phone", "")
        if not str(raw_phone).strip():
            return Response({"error": "Phone number is required"}, status=400)

        phone_number = self._normalize_phone_number(raw_phone)
        if phone_number is None:
            return Response(
                {
                    "error": (
                        "Invalid phone number format. Use 07xxxxxxxx, 01xxxxxxxx, "
                        "+2547xxxxxxxx, +2541xxxxxxx, 2547xxxxxxxx, or 2541xxxxxxx."
                    )
                },
                status=400,
            )

        try:
            cart = Cart.objects.prefetch_related("items__product").get(customer=profile)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=404)

        if not cart.items.exists():
            return Response({"error": "Your cart is empty"}, status=400)

        cart_items = list(cart.items.all())
        for item in cart_items:
            if item.product is None or not item.product.is_available:
                return Response(
                    {"error": f"{item.product.name if item.product else 'A product'} is no longer available"},
                    status=400,
                )
            if item.quantity > item.product.stock_quantity:
                return Response(
                    {"error": f"Not enough stock for {item.product.name}. Available: {item.product.stock_quantity}"},
                    status=400,
                )

        total_amount = sum(item.product.price * item.quantity for item in cart_items)
        if total_amount <= 0:
            return Response({"error": "Invalid order amount"}, status=400)

        order = Order.objects.create(
            customer=profile,
            total_amount=total_amount,
            is_paid=False,
            status="pending",
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price,
            )

        if getattr(settings, "MPESA_SIMULATE_SUCCESS", False):
            self._simulate_successful_payment(order)
            return Response(
                {
                    "success": True,
                    "message": "TEST MODE: Payment simulated successfully. Order is awaiting seller approval.",
                    "order_id": order.id,
                    "simulated": True,
                    "payment_reference": order.payment_reference,
                }
            )

        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password_str = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
            password = base64.b64encode(password_str.encode("utf-8")).decode("utf-8")

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
                "TransactionDesc": f"Payment for order #{order.id}",
            }

            stk_url = (
                "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
                if settings.MPESA_ENVIRONMENT == "sandbox"
                else "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
            )

            headers = {
                "Authorization": f"Bearer {self.get_access_token()}",
                "Content-Type": "application/json",
            }
            response = requests.post(stk_url, json=payload, headers=headers, timeout=30)

            if response.status_code != 200:
                return Response(
                    {
                        "success": True,
                        "message": "Order saved as pending. STK push was not confirmed, but the seller can still approve it.",
                        "warning": "Failed to connect to M-Pesa",
                        "order_id": order.id,
                        "status": response.status_code,
                        "detail": response.text,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )

            resp_data = response.json()
            if resp_data.get("ResponseCode") == "0":
                checkout_request_id = resp_data.get("CheckoutRequestID")
                payment_reference = checkout_request_id or f"STK-{order.id}-{timestamp}"
                self._complete_order(order, payment_reference)
                return Response(
                    {
                        "success": True,
                        "message": "Payment request sent successfully. Order is awaiting seller approval.",
                        "order_id": order.id,
                        "checkout_request_id": checkout_request_id,
                        "merchant_request_id": resp_data.get("MerchantRequestID"),
                    }
                )

            return Response(
                {
                    "success": True,
                    "message": "Order saved as pending. STK push was not confirmed, but the seller can still approve it.",
                    "warning": resp_data.get("ResponseDescription", "Daraja rejected request"),
                    "order_id": order.id,
                    "daraja_response": resp_data,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except requests.RequestException as exc:
            return Response(
                {
                    "success": True,
                    "message": "Order saved as pending. M-Pesa could not be reached, but the seller can still approve it.",
                    "warning": f"M-Pesa request failed: {exc}",
                    "order_id": order.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            return Response(
                {
                    "success": True,
                    "message": "Order saved as pending, but there was a server issue confirming the STK push.",
                    "warning": f"Server error: {exc}",
                    "order_id": order.id,
                },
                status=status.HTTP_202_ACCEPTED,
            )


class MpesaCallback(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        try:
            callback = request.data.get("Body", {}).get("stkCallback", {})
            if callback.get("ResultCode") != 0:
                return Response({"ResultCode": 0, "ResultDesc": "Accepted"})

            metadata = callback.get("CallbackMetadata", {}).get("Item", [])
            receipt = next(
                (item["Value"] for item in metadata if item.get("Name") == "MpesaReceiptNumber"),
                None,
            )

            order = Order.objects.filter(is_paid=False).order_by("-created_at").first()
            if order:
                CheckoutView()._complete_order(order, receipt or order.payment_reference or f"MPESA-{order.id}")

            return Response({"ResultCode": 0, "ResultDesc": "Accepted"})
        except Exception as exc:
            return Response({"ResultCode": 1, "ResultDesc": str(exc)}, status=500)


class CustomerOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = None

    def get_queryset(self):
        profile = getattr(self.request.user, "userprofile", None)
        if profile is None or profile.role != "customer":
            return Order.objects.none()
        return (
            Order.objects.filter(customer=profile)
            .exclude(status="completed")
            .prefetch_related("items__product", "customer__user")
            .order_by("-created_at")
        )


class OwnerOrdersView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = None

    def get_queryset(self):
        profile = getattr(self.request.user, "userprofile", None)
        if profile is None or profile.role != "owner":
            return Order.objects.none()
        queryset = (
            Order.objects.filter(items__product__owner=profile)
            .distinct()
            .prefetch_related("items__product", "customer__user")
            .order_by("-created_at")
        )
        approval_filter = self.request.query_params.get("approval")
        if approval_filter == "approved":
            queryset = queryset.filter(status="approved")
        elif approval_filter == "unapproved":
            queryset = queryset.filter(status="pending")
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["owner_profile"] = self.request.user.userprofile
        return context


class OwnerApproveOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return Response({"error": "Profile not found"}, status=400)
        if profile.role != "owner":
            return Response({"error": "Not authorized"}, status=403)

        try:
            order = (
                Order.objects.filter(items__product__owner=profile)
                .distinct()
                .prefetch_related("items__product")
                .get(pk=pk)
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)

        if order.status == "approved":
            return Response({"message": "Order already approved"}, status=200)
        if order.status == "cancelled":
            return Response({"error": "Cancelled orders cannot be approved"}, status=400)

        order.status = "approved"
        order.save(update_fields=["status", "updated_at"])
        return Response({"message": "Order approved successfully"})


class OwnerStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "userprofile", None)
        if profile is None:
            return Response({"error": "Profile not found"}, status=400)
        if profile.role != "owner":
            return Response({"error": "Not authorized"}, status=403)

        products = Product.objects.filter(owner=profile)
        low_stock = products.filter(stock_quantity__lt=10).count()
        total_products = products.count()

        owner_order_items = OrderItem.objects.filter(
            order__status="approved",
            product__owner=profile,
        )
        total_sales = owner_order_items.aggregate(
            total=Sum(
                F("quantity") * F("price_at_purchase"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"] or Decimal("0.00")
        total_orders = owner_order_items.values("order_id").distinct().count()

        payload = {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "low_stock_products": low_stock,
            "total_products": total_products,
        }
        return Response(OwnerStatsSerializer(payload).data)
