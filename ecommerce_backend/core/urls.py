from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, LoginView
from .views import AddProductView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),

    # Auth endpoints
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/',    LoginView.as_view(),    name='login'),

    # Optional: built-in token obtain (you can keep or remove)
    # path('auth/token/', obtain_auth_token, name='api_token_auth'),
    path('products/add/', AddProductView.as_view(), name='add-product'),
]