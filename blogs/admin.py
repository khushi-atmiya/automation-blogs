from django.contrib import admin
from .models import MainCategory, Category, BlogPost

admin.site.register(MainCategory)
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_main_categories')
    
    def get_main_categories(self, obj):
        return ", ".join([mc.name for mc in obj.main_categories.all()])
    get_main_categories.short_description = 'Main Categories'

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'main_category', 'category')
    prepopulated_fields = {'slug': ('title',)}
