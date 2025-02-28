from django.db import models


# Initialize Firestore DB


class GeneratedImage(models.Model):
    prompt = models.TextField()
    image = models.ImageField(upload_to='generated_images/')
    leonardo_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for: {self.prompt[:10]}.."
    




