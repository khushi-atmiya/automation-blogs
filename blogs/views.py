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
        return BlogPost.objects.filter(main_category__name__iexact=main_category_name)

class BlogPostByCategoryNameView(generics.ListAPIView):
    serializer_class = BlogPostSerializer

    def get_queryset(self):
        category_name = self.kwargs['category_name']
        return BlogPost.objects.filter(category__name__iexact=category_name)

class BlogPostByCombinedFilterView(generics.ListAPIView):
    serializer_class = BlogPostSerializer

    def get_queryset(self):
        main_category_name = self.kwargs['main_category_name']
        category_name = self.kwargs['category_name']
        return BlogPost.objects.filter(
            main_category__name__iexact=main_category_name,
            category__name__iexact=category_name
        )

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
