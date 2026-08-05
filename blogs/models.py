from django.db import models

class MainCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Category(models.Model):
    main_categories = models.ManyToManyField(MainCategory, related_name='categories', blank=True)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class BlogPost(models.Model):
    main_categories = models.ManyToManyField(MainCategory, related_name='blog_posts', blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    description = models.TextField(default='')
    author = models.CharField(max_length=255, blank=True, null=True, default='')
    blog_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
import requests
import re

@receiver(m2m_changed, sender=Category.main_categories.through)
def sync_blog_posts_on_category_m2m_change(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        posts = BlogPost.objects.filter(category=instance)
        for post in posts:
            post.main_categories.add(*pk_set)
    elif action == "post_remove":
        posts = BlogPost.objects.filter(category=instance)
        for post in posts:
            post.main_categories.remove(*pk_set)
    elif action == "post_clear":
        posts = BlogPost.objects.filter(category=instance)
        for post in posts:
            post.main_categories.clear()

HOSTINGER_SECRET_TOKEN = 'blogs_sec_key_8f7d9a1b2c4e6f8a0b2c4e6f8a0b2c4e'

def send_meta_webhook_for_post(instance):
    """Dynamically post Meta HTML webhook to all assigned domains (40-50 domains supported)."""
    try:
        image_url = ""
        if instance.image:
            image_url = instance.image.url if hasattr(instance.image, 'url') else str(instance.image)

        raw_desc = instance.description or instance.title
        clean_desc = re.sub(r'<[^>]+>', ' ', raw_desc)
        clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
        excerpt = clean_desc[:160] if clean_desc else instance.title

        domains = instance.main_categories.all()
        domain_names = [d.name.strip() for d in domains if d.name]

        if not domain_names:
            domain_names = ['ufreegames.fun']

        for domain in domain_names:
            if not domain.startswith('http://') and not domain.startswith('https://'):
                target_url = f"https://{domain}/upload.php"
            else:
                target_url = f"{domain.rstrip('/')}/upload.php"

            payload = {
                'token': HOSTINGER_SECRET_TOKEN,
                'slug': instance.slug,
                'title': instance.title,
                'excerpt': excerpt,
                'image': image_url,
                'domain': domain
            }

            try:
                res = requests.post(target_url, data=payload, timeout=5)
                print(f"Sent meta webhook to {target_url}: Status {res.status_code}")
            except Exception as err:
                print(f"Failed sending meta webhook to {target_url}: {err}")
    except Exception as e:
        print(f"Hostinger Meta Upload Error: {e}")

@receiver(post_save, sender=BlogPost)
def trigger_hostinger_meta_upload(sender, instance, created, **kwargs):
    send_meta_webhook_for_post(instance)

@receiver(m2m_changed, sender=BlogPost.main_categories.through)
def trigger_hostinger_meta_upload_m2m(sender, instance, action, **kwargs):
    if action in ["post_add", "post_set"]:
        send_meta_webhook_for_post(instance)


