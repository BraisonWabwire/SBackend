from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, LoginView
from .views import AddProductView,ProductListView,AddToCartView,CartView,RemoveCartItemView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),

    # Auth endpoints
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/',    LoginView.as_view(),    name='login'),

    # Optional: built-in token obtain (you can keep or remove)
    # path('auth/token/', obtain_auth_token, name='api_token_auth'),
    path('products/add/', AddProductView.as_view(), name='add-product'),
    path('products/', ProductListView.as_view(), name='product-list'),


    # Cart item
    path('cart/add/', AddToCartView.as_view(), name='add-to-cart'),
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/items/<int:pk>/', RemoveCartItemView.as_view(), name='remove-cart-item'),
]