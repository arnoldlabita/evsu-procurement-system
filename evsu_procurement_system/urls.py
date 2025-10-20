"""
URL configuration for evsu_procurement_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

# ✅ Smart redirect function for root URL
def root_redirect(request):
    if request.user.is_authenticated:
        return redirect("procurement:dashboard")
    return redirect("login")

urlpatterns = [
    path("admin/", admin.site.urls),

    # 🔒 Smart root redirect
    path("", root_redirect, name="root_redirect"),

    # Authentication routes
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # Procurement app URLs (namespace must match your app_name in procurement/urls.py)
    path("procurement/", include(("procurement.urls", "procurement"), namespace="procurement")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)