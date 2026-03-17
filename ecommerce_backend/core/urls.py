# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import all your views
from .views import (
    RegisterView,
    LoginView,
    ProductViewSet,          # ← use ViewSet instead of separate list/add
    AddToCartView,
    CartView,
    RemoveCartItemView,
    CheckoutView,
    MpesaCallback,
    CustomerOrdersView
    
    # UpdateCartItemView,      # optional – for quantity update
)

# Create router
router = DefaultRouter()

# Register ViewSets (automatic CRUD endpoints)
router.register(r'products', ProductViewSet, basename='product')

# Manual paths for non-standard views
urlpatterns = [
    # Auth (custom views, not ViewSets)
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),

    # Cart (custom actions)
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/items/<int:pk>/', RemoveCartItemView.as_view(), name='remove-cart-item'),

    # Order 
    path('orders/', CustomerOrdersView.as_view(), name='customer-orders'),
    
    # Optional: if you add PATCH for quantity update
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('mpesa/callback/', MpesaCallback.as_view(), name='mpesa-callback'),

    # path('cart/items/<int:pk>/update/', UpdateCartItemView.as_view(), name='update-cart-item'),

    # Include all router-generated URLs
    path('', include(router.urls)),
]