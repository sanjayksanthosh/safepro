"""URL configuration for safepro_backend project.

In production the built React app (frontend/dist) is served at the root;
/api/* stays with the Django API.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('products.urls')),
]

if not settings.DEBUG:
    # Serve the single-page app. Static assets (/assets/...) are served by
    # WhiteNoise from STATIC_ROOT (collectstatic copies frontend/dist there).
    urlpatterns += [
        path('', TemplateView.as_view(template_name='index.html')),
    ]
