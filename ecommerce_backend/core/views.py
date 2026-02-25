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