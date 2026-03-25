from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Cart, CartItem, Order, OrderItem, Product, UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirm password")
    role = serializers.ChoiceField(
        choices=[("owner", "Shop Owner"), ("customer", "Customer")],
        write_only=True,
    )
    contact_info = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "password2", "role", "contact_info"]

    def validate(self, data):
        if data["password"] != data["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        role = validated_data.pop("role")
        contact_info = validated_data.pop("contact_info", "")
        password = validated_data.pop("password")
        validated_data.pop("password2")

        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(
            user=user,
            role=role,
            contact_info=contact_info,
        )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})

    def validate(self, data):
        user = authenticate(**data)
        if user and user.is_active:
            return user
        raise serializers.ValidationError("Invalid username or password.")


class OwnerSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    role = serializers.CharField(read_only=True)


class CustomerSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    contact_info = serializers.CharField(read_only=True)


class ProductSerializer(serializers.ModelSerializer):
    owner = OwnerSummarySerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "owner",
            "name",
            "slug",
            "description",
            "price",
            "stock_quantity",
            "barcode",
            "sku",
            "image",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "slug", "created_at", "updated_at"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_available=True, stock_quantity__gt=0),
        source="product",
        write_only=True,
    )
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "subtotal", "added_at"]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "total_price", "created_at", "updated_at"]

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_price(self, obj):
        total = sum(item.subtotal for item in obj.items.select_related("product"))
        return f"{Decimal(total):.2f}"


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
        default="Product (removed)",
    )
    product_image = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "product_image",
            "quantity",
            "price_at_purchase",
            "subtotal",
        ]

    def get_product_image(self, obj):
        if obj.product and obj.product.image:
            request = self.context.get("request")
            if request is not None:
                return request.build_absolute_uri(obj.product.image.url)
            return obj.product.image.url
        return None

    def get_subtotal(self, obj):
        return f"{obj.subtotal:.2f}"


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    customer = CustomerSummarySerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "created_at",
            "updated_at",
            "customer",
            "total_amount",
            "status",
            "is_paid",
            "payment_reference",
            "items",
        ]

    def get_items(self, obj):
        owner_profile = self.context.get("owner_profile")
        items = obj.items.all()
        if owner_profile is not None:
            items = [item for item in items if item.product and item.product.owner_id == owner_profile.id]

        serializer = OrderItemSerializer(
            items,
            many=True,
            context=self.context,
        )
        return serializer.data

    def get_total_amount(self, obj):
        owner_profile = self.context.get("owner_profile")
        if owner_profile is None:
            return f"{obj.total_amount:.2f}"

        owner_total = sum(
            item.subtotal
            for item in obj.items.all()
            if item.product and item.product.owner_id == owner_profile.id
        )
        return f"{owner_total:.2f}"


class OwnerStatsSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_orders = serializers.IntegerField(default=0)
    low_stock_products = serializers.IntegerField(default=0)
    total_products = serializers.IntegerField(default=0)
