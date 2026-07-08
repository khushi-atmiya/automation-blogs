import json
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
    list_display = ('title', 'get_main_categories', 'category')
    prepopulated_fields = {'slug': ('title',)}

    def get_main_categories(self, obj):
        return ", ".join([mc.name for mc in obj.main_categories.all()])
    get_main_categories.short_description = 'Main Categories'

    class Media:
        js = ('admin/js/filter_category.js',)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Category → main categories map banavo
        mains_by_category = {}
        for cat in Category.objects.prefetch_related('main_categories').all():
            mains_by_category[str(cat.id)] = [mc.id for mc in cat.main_categories.all()]
        extra_context['mains_by_category_json'] = json.dumps(mains_by_category)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Badhi categories show karo - JS dynamically filter karsey
        form.base_fields['category'].queryset = Category.objects.all()
        return form
