"""URL configuration for mypro project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('myapp.urls')),
]

# Serve uploaded product images while developing (DEBUG only)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
