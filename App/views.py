import requests
import json
import time
import tempfile
import os
from django.http import JsonResponse
from django.conf import settings
from django.core.files import File
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import GeneratedImage
from .serializers import GeneratedImageSerializer, ImageGenerationSerializer
from datetime import datetime


from firebase_admin import firestore
db = firestore.client()
doc_ref = db.collection('GeneratedImage').document()
class Load_models(APIView):
    def get(self, request):
        url = "https://cloud.leonardo.ai/api/rest/v1/platformModels"

        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {settings.LEONARDO_AI_API}"
        }

        res = requests.get(url, headers=headers)
        return JsonResponse(res.json(), safe=False)



class GenerateImageView(APIView):
    def download_image(self, url, file_path):
        """
        Download an image from a URL without using authentication headers.
        S3 URLs provided by Leonardo AI are pre-signed and don't need the Bearer token.
        """
        try:
            # Download the image without authorization headers
            # S3 pre-signed URLs already contain the necessary auth info
            response = requests.get(url, stream=True)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            print(f"Error downloading image: {str(e)}")
            return False
    
    def post(self, request):
        serializer = ImageGenerationSerializer(data=request.data)
        if serializer.is_valid():
            prompt = serializer.validated_data['prompt']
            # negative_prompt = serializer.validated_data.get('negative_prompt', '')
            model_id = serializer.validated_data.get('model_id', 'b24e16ff-06e3-43eb-8d33-4416c2d75876')
            # API headers
            headers = {
                "Authorization": f"Bearer {settings.LEONARDO_AI_API}",
                "Content-Type": "application/json"
            }
            
            generation_data = {
                "prompt": prompt,
                # "negative_prompt": negative_prompt,
                "modelId": model_id,
                "num_images": 1,
                "width": 512,
                "height": 512,
            }
            
            # Debug the API URL and headers
            # print(f"API Key: {settings.LEONARDO_AI_API}")
            print(f"Request data: {generation_data}")
            
            # Start generation request
            try:
                response = requests.post(
                    "https://cloud.leonardo.ai/api/rest/v1/generations",
                    headers=headers,
                    data=json.dumps(generation_data)
                )
                
                # print(f"Generation response code: {response.status_code}")
                # print(f"Generation response: {response.text}")
                
                response.raise_for_status()  # Raise exception for 4XX/5XX responses
            except requests.exceptions.RequestException as e:
                return Response(
                    {"error": f"Failed to initiate image generation: {str(e)}", "details": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract the generation ID from the response
            try:
                response_data = response.json()
                generation_id = response_data['sdGenerationJob']['generationId']
                print(f"Generation ID: {generation_id}")
            except (KeyError, json.JSONDecodeError) as e:
                return Response(
                    {"error": f"Unexpected response format from Leonardo API: {str(e)}", "details": response.text},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Poll for completion
            max_attempts = 60  # 5 minutes with 5-second intervals
            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                print(f"Checking status attempt {attempts}")
                time.sleep(5)  # Wait 5 seconds between checks
                
                # Check generation status
                try:
                    status_response = requests.get(
                        f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
                        headers=headers
                    )
                    
                    print(f"Status response code: {status_response.status_code}")
                    print(f"Status response: {status_response.text}")
                    
                    status_response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(f"Error checking status: {str(e)}")
                    continue
                
                # Parse the response
                try:
                    generation_data = status_response.json()
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {str(e)}")
                    continue
                
                # Check generation status
                if 'generations_by_pk' in generation_data:
                    generation_status = generation_data['generations_by_pk'].get('status')
                    print(f"Current status: {generation_status}")
                    
                    if generation_status == 'COMPLETE':
                        # Check if there are generated images
                        generated_images = generation_data['generations_by_pk'].get('generated_images', [])
                        
                        if not generated_images:
                            print("No images found in the response")
                            continue
                        
                        # Get the first image URL
                        try:
                            image_url = generated_images[0]['url']
                            print(f"Image URL: {image_url}")
                            
                            # Create a temporary file path
                            temp_file_path = os.path.join(tempfile.gettempdir(), f"leonardo_{generation_id}.png")
                            
                            # Download the image without auth headers (S3 pre-signed URL)
                            if not self.download_image(image_url, temp_file_path):
                                return Response(
                                    {"error": "Failed to download image"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                                )
                            
                            # Save to our model
                            generated_image = GeneratedImage(
                                prompt=prompt,
                                leonardo_id=generation_id
                            )
                            doc_ref.set({
                                'prompt': f'{prompt}',
                                'leonardo_id': f'{generation_id}'
                            })
                            with open(temp_file_path, 'rb') as f:
                                generated_image.image.save(
                                    f"leonardo_{generation_id}.png", 
                                    File(f)
                                )
                            generated_image.save()
                            doc_ref.set({'image':f'{generated_image}', 'created_at': f'{datetime.now()}'})
                            # Clean up
                            os.remove(temp_file_path)
                            
                            # Return success
                            serializer = GeneratedImageSerializer(generated_image, context={'request': request})
                            return Response(serializer.data, status=status.HTTP_201_CREATED)
                            
                        except (IndexError, KeyError) as e:
                            return Response(
                                {"error": f"Image URL not found in response: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )
                        except Exception as e:
                            print(f"Error processing image: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            return Response(
                                {"error": f"Error processing image: {str(e)}"}, 
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )
                    elif generation_status == 'FAILED':
                        return Response(
                            {"error": "Image generation failed on Leonardo AI side"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    print(f"Unexpected response structure: {generation_data}")
            
            return Response(
                {"error": "Timeout while waiting for image generation"},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ListGeneratedImagesView(APIView):
    def get(self, request):
        images = GeneratedImage.objects.all().order_by('-created_at')
        serializer = GeneratedImageSerializer(images,  many=True, context= 
        {'request': request})
        return Response(serializer.data)