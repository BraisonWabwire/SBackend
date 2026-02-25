# core/models.py
from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=[('owner', 'Owner'), ('customer', 'Customer')],
        default='customer'
    )
    contact_info = models.CharField(max_length=100, blank=True)  # e.g. phone number

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    # Optional: convenient property
    @property
    def username(self):
        return self.user.username


from django.core.validators import MinValueValidator
from django.utils.text import slugify

class Product(models.Model):
    owner = models.ForeignKey(
        'UserProfile',
        on_delete=models.CASCADE,
        related_name='products',
        limit_choices_to={'role': 'owner'}
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    barcode = models.CharField(max_length=50, blank=True, null=True, unique=True)
    sku = models.CharField(max_length=50, blank=True, null=True, unique=True)
    image = models.ImageField(upload_to='products/%Y/%m/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['owner', 'is_available']),
            models.Index(fields=['barcode']),
            models.Index(fields=['sku']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def reduce_stock(self, quantity):
        if self.stock_quantity < quantity:
            raise ValueError(f"Not enough stock: {self.stock_quantity} available")
        self.stock_quantity -= quantity
        self.save(update_fields=['stock_quantity'])

# core/models.py (add after Order/OrderItem)

class Cart(models.Model):
    """
    Shopping cart for customers
    """
    customer = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'customer'},
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.customer.username}"

    def total_items(self):
        return self.items.count()

    def total_price(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')  # one product per cart

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    @property
    def subtotal(self):
        return self.quantity * self.product.price