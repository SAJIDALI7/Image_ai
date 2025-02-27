from rest_framework import serializers
from .models import GeneratedImage

class GeneratedImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedImage
        fields = ['id', 'prompt', 'image', 'leonardo_id', 'created_at']

class ImageGenerationSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True)
    # negative_prompt = serializers.CharField(required=False, allow_blank=True)
    model_id = serializers.CharField(required=False, allow_blank=True)