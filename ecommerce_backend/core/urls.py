from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AddToCartView,
    CartItemView,
    CartView,
    CheckoutView,
    CustomerOrdersView,
    LoginView,
    MpesaCallback,
    OwnerApproveOrderView,
    OwnerOrdersView,
    OwnerStatsView,
    ProductViewSet,
    RegisterView,
)

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("cart/add/", AddToCartView.as_view(), name="add-to-cart"),
    path("cart/", CartView.as_view(), name="cart-detail"),
    path("cart/items/<int:pk>/", CartItemView.as_view(), name="cart-item-detail"),
    path("orders/", CustomerOrdersView.as_view(), name="customer-orders"),
    path("owner/orders/", OwnerOrdersView.as_view(), name="owner-orders"),
    path("owner/orders/<int:pk>/approve/", OwnerApproveOrderView.as_view(), name="owner-approve-order"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("ownerStats/", OwnerStatsView.as_view(), name="owner-stats"),
    path("mpesa/callback/", MpesaCallback.as_view(), name="mpesa-callback"),
    path("", include(router.urls)),
]
