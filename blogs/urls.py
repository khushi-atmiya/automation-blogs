from django.urls import path
from .views import (
    MainCategoryListCreateView, CategoryListCreateView, BlogPostListCreateView, 
    BlogPostDetailView, BlogPostByMainCategoryNameView, BlogPostByCategoryNameView,
    BlogPostByCombinedFilterView, CategoriesByMainCategoryView
)

urlpatterns = [
    path('main-categories/', MainCategoryListCreateView.as_view(), name='main-category-list-create'),
    path('categories/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('blog-posts/', BlogPostListCreateView.as_view(), name='blog-post-list-create'),
    path('blog-posts/<int:pk>/', BlogPostDetailView.as_view(), name='blog-post-detail'),
    path('blog-posts/main-category/<str:main_category_name>/', BlogPostByMainCategoryNameView.as_view(), name='blog-post-by-main-category'),
    path('blog-posts/category/<str:category_name>/', BlogPostByCategoryNameView.as_view(), name='blog-post-by-category'),
    path('blog-posts/filter/<str:main_category_name>/<str:category_name>/', BlogPostByCombinedFilterView.as_view(), name='blog-post-by-combined-filter'),
    # Admin JS mate - categories by main category ID
    path('categories-by-main/<int:main_category_id>/', CategoriesByMainCategoryView.as_view(), name='categories-by-main'),
]
