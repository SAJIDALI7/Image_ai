from django.contrib import admin
from .models import GeneratedImage
@admin.register(GeneratedImage)
class AdminImage_gen_propmt(admin.ModelAdmin):
    list_display = ['id', 'prompt']
