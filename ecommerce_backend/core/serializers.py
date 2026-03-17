from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import UserProfile
from decimal import Decimal

# ────────────────────────────────────────────────
# Signup / Registration Serializer
# ────────────────────────────────────────────────
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirm password")
    role = serializers.ChoiceField(choices=[('owner', 'Shop Owner'), ('customer', 'Customer')], write_only=True)
    contact_info = serializers.CharField(max_length=100, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2', 'role', 'contact_info']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        role = validated_data.pop('role')
        contact_info = validated_data.pop('contact_info', '')
        password = validated_data.pop('password')
        validated_data.pop('password2')

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        UserProfile.objects.create(
            user=user,
            role=role,
            contact_info=contact_info
        )

        return user


# ────────────────────────────────────────────────
# Login Serializer (used only for documentation / validation)
# ────────────────────────────────────────────────
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Invalid username or password.")


from .models import Product


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'price',
            'stock_quantity',
            'barcode',
            'sku',
            'image',
        ]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value


from .models import CartItem
from .models import Cart
# core/serializers.py
# core/serializers.py (update or add)
from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'stock_quantity',
            'barcode',
            'sku',
            'image',
            'is_available',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']  # owner is set automatically



class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity', 'subtotal', 'added_at']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, min_value=Decimal('0.00'))

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_items', 'total_price', 'created_at', 'updated_at']



 # serializers.py

from rest_framework import serializers
from .models import OrderItem, Order, Product

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source='product.name', 
        read_only=True,
        default='Product (removed)'
    )
    
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id',                    # ← important: include id for React keys
            'product_name',
            'product_image',
            'quantity',
            'price_at_purchase'
        ]

    def get_product_image(self, obj):
        """
        Safely return the full image URL or None
        """
        if obj.product and obj.product.image:
            # This gives http://127.0.0.1:8000/media/... in development
            return obj.product.image.url
        return None


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'created_at',
            'total_amount',
            'status',
            'is_paid',
            'payment_reference',
            'items'
        ]