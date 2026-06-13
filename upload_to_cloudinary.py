import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blogsBackend.settings')
django.setup()

from blogs.models import BlogPost
from django.core.files import File

def upload_images():
    posts = BlogPost.objects.exclude(image='')
    for post in posts:
        if post.image and post.image.name:
            # Check if this image name is already a cloudinary format or just local
            # If it's already uploaded by another run, we might want to skip, but it's fine
            filename = os.path.basename(post.image.name)
            local_path = os.path.join('media', 'blog_images', filename)
            
            if os.path.exists(local_path):
                print(f"Uploading {filename} to Cloudinary...")
                with open(local_path, 'rb') as f:
                    # Save to Cloudinary using Django's File
                    # This will also update the live database with the new cloudinary image name
                    post.image.save(filename, File(f), save=True)
            else:
                print(f"Local file missing: {local_path}")

if __name__ == "__main__":
    upload_images()
    print("Done uploading all images!")
