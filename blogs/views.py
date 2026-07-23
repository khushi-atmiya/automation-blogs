from django.shortcuts import render
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import MainCategory, Category, BlogPost
from .serializers import MainCategorySerializer, CategorySerializer, BlogPostSerializer

class MainCategoryListCreateView(generics.ListCreateAPIView):
    queryset = MainCategory.objects.all()
    serializer_class = MainCategorySerializer

class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class BlogPostListCreateView(generics.ListCreateAPIView):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer

class BlogPostDetailView(generics.RetrieveAPIView):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer

class BlogPostByMainCategoryNameView(generics.ListAPIView):
    serializer_class = BlogPostSerializer

    def get_queryset(self):
        main_category_name = self.kwargs['main_category_name']
        return BlogPost.objects.filter(main_categories__name__iexact=main_category_name).distinct()

class BlogPostByCategoryNameView(generics.ListAPIView):
    serializer_class = BlogPostSerializer

    def get_queryset(self):
        category_name = self.kwargs['category_name']
        return BlogPost.objects.filter(category__name__iexact=category_name).distinct()

class BlogPostByCombinedFilterView(generics.ListAPIView):
    serializer_class = BlogPostSerializer

    def get_queryset(self):
        main_category_name = self.kwargs['main_category_name']
        category_name = self.kwargs['category_name']
        return BlogPost.objects.filter(
            main_categories__name__iexact=main_category_name,
            category__name__iexact=category_name
        ).distinct()

# Admin JS mate - selected main category na j categories return karo
class CategoriesByMainCategoryView(APIView):
    def get(self, request, main_category_id):
        categories = Category.objects.filter(main_categories__id=main_category_id).values('id', 'name')
        return Response(list(categories))

class CategoryByMainCategoryQueryView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.all()
        main_category_name = self.request.query_params.get('main_category', None)
        if main_category_name:
            queryset = queryset.filter(main_categories__name__iexact=main_category_name)
        return queryset


# -------------------------------------------------------------
# HTML AND XML ENDPOINTS FOR STATIC FRONTEND BYPASS
# -------------------------------------------------------------
from django.views import View
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.utils.html import strip_tags
from django.template.loader import render_to_string
from django.contrib.syndication.views import Feed
import datetime
import re

def get_current_domain(request):
    # Retrieve host forwarded by Cloudflare Worker
    host = request.META.get('HTTP_X_FORWARDED_HOST', request.META.get('HTTP_HOST', ''))
    # Strip any www. prefix and lower case
    clean_host = host.replace('www.', '').strip().lower()
    return clean_host or 'urbanloanhub.store' # Default fallback for local testing

class BlogPostDetailHtmlView(View):
    def get(self, request, slug):
        domain = get_current_domain(request)
        
        # Get post associated with this domain (MainCategory name) and slug
        blog = get_object_or_404(
            BlogPost.objects.prefetch_related('main_categories').select_related('category'),
            slug=slug,
            main_categories__name__iexact=domain
        )
        
        # Clean HTML tags from description to construct plain text SEO description
        raw_description = blog.description
        if isinstance(raw_description, list):
            raw_description = " ".join(raw_description)
        
        clean_text = strip_tags(raw_description)
        # Limit to 155 characters for search engines
        seo_description = re.sub(r'\s+', ' ', clean_text).strip()[:155] + "..."
        
        # Fetch related blogs in same category, exclude current
        related_blogs = BlogPost.objects.filter(
            main_categories__name__iexact=domain,
            category=blog.category
        ).exclude(id=blog.id).order_by('-created_at').distinct()[:3]
        
        # Fetch recent blogs for sidebar
        recent_blogs = BlogPost.objects.filter(
            main_categories__name__iexact=domain
        ).order_by('-created_at').distinct()[:5]

        # Handle Cloudinary / Local media image optimization
        blog_image_url = ""
        if blog.image:
            url = blog.image.url
            if 'res.cloudinary.com' in url and '/upload/' in url:
                blog_image_url = url.replace('/upload/', '/upload/f_auto,q_auto,w_1200/')
            else:
                blog_image_url = url
        
        context = {
            'blog': blog,
            'seo_description': seo_description,
            'related_blogs': related_blogs,
            'recent_blogs': recent_blogs,
            'domain': domain,
            'blog_image_url': blog_image_url,
            'formatted_date': blog.blog_date or blog.created_at.date()
        }
        
        return render(request, 'blogs/blog_detail.html', context)
 
class DynamicSitemapView(View):
    def get(self, request):
        domain = get_current_domain(request)
        
        posts = BlogPost.objects.filter(
            main_categories__name__iexact=domain
        ).order_by('-created_at').distinct()

        # List of your static Next.js paths that reside on Hostinger
        static_paths = [
            '',
            '/games/',
            '/download/',
            '/about/',
            '/contact/',
            '/privacy-policy/',
        ]

        context = {
            'domain': domain,
            'posts': posts,
            'static_paths': static_paths,
            'today': datetime.date.today().isoformat()
        }

        sitemap_xml = render_to_string('blogs/sitemap.xml', context)
        return HttpResponse(sitemap_xml, content_type='application/xml')

class DynamicRobotsTxtView(View):
    def get(self, request):
        domain = get_current_domain(request)
        content = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin/

Sitemap: https://{domain}/sitemap.xml
"""
        return HttpResponse(content, content_type='text/plain')

class DynamicRssFeedView(Feed):
    def get_object(self, request):
        self.domain = get_current_domain(request)
        return self.domain

    def title(self, obj):
        return f"Blog Feed | {obj}"

    def link(self, obj):
        return f"https://{obj}/blog/"

    def description(self, obj):
        return f"Stay updated with the latest articles and stories from {obj}."

    def items(self, obj):
        return BlogPost.objects.filter(
            main_categories__name__iexact=obj
        ).order_by('-created_at').distinct()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        desc = item.description
        if isinstance(desc, list):
            desc = " ".join(desc)
        return strip_tags(desc)[:200] + "..."

    def item_link(self, item):
        domain = getattr(self, 'domain', 'urbanloanhub.store')
        return f"https://{domain}/blog/{item.slug}/"


import threading
from django.core.management import call_command
from django.http import JsonResponse
import os

def run_daily_blogs_webhook(request):
    # Security check: Ensure only our cron-job.org task can trigger this
    secret = request.GET.get("secret")
    expected_secret = os.environ.get("CRON_SECRET", "automation123")
    
    if secret != expected_secret:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # Run the command in a background thread so the HTTP request doesn't timeout
    def run_command():
        try:
            call_command("generate_blogs")
        except Exception as e:
            print(f"Error running generate_blogs: {e}")

    thread = threading.Thread(target=run_command)
    thread.start()

    return JsonResponse({"status": "success", "message": "Blog generation started in background"})

