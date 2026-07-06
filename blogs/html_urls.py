from django.urls import path
from .views import BlogPostDetailHtmlView, DynamicSitemapView, DynamicRobotsTxtView, DynamicRssFeedView

urlpatterns = [
    path('blog/<slug:slug>/', BlogPostDetailHtmlView.as_view(), name='blog-detail-html'),
    path('sitemap.xml', DynamicSitemapView.as_view(), name='dynamic-sitemap'),
    path('robots.txt', DynamicRobotsTxtView.as_view(), name='dynamic-robots'),
    path('rss.xml', DynamicRssFeedView(), name='dynamic-rss'),
]
