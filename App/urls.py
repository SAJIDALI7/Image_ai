from django.urls import path
from .views import GenerateImageView, ListGeneratedImagesView
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('generate_image/', GenerateImageView.as_view(), name='generate_image'),
    path('images/', ListGeneratedImagesView.as_view(), name='list_images'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)