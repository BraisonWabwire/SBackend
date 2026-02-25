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