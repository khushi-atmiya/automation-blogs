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

from django.db.models.signals import m2m_changed
from django.dispatch import receiver

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
