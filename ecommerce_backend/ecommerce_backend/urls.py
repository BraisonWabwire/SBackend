from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token  # built-in view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),  # your API routers

    # Token auth endpoints
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),  # POST username+password → get token
    path('api-auth/', include('rest_framework.urls')),                   # optional: browsable API login/logout
]