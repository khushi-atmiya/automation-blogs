from rest_framework import serializers
from .models import MainCategory, Category, BlogPost

class MainCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MainCategory
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    main_categories = serializers.SlugRelatedField(many=True, slug_field='name', queryset=MainCategory.objects.all())
    
    class Meta:
        model = Category
        fields = ['id', 'main_categories', 'name']

class BlogPostSerializer(serializers.ModelSerializer):
    main_categories = serializers.SlugRelatedField(many=True, slug_field='name', queryset=MainCategory.objects.all())
    category = serializers.SlugRelatedField(slug_field='name', queryset=Category.objects.all())

    class Meta:
        model = BlogPost
        fields = '__all__'
