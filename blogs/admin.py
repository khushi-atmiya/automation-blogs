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
    list_display = ('title', 'main_category', 'category')
    prepopulated_fields = {'slug': ('title',)}

    class Media:
        js = ('admin/js/filter_category.js',)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Main category → categories map banavo
        categories_by_main = {}
        for cat in Category.objects.prefetch_related('main_categories').all():
            for mc in cat.main_categories.all():
                key = str(mc.id)
                if key not in categories_by_main:
                    categories_by_main[key] = []
                categories_by_main[key].append({'id': cat.id, 'name': cat.name})
        extra_context['categories_by_main_json'] = json.dumps(categories_by_main)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Badhi categories show karo - JS dynamically filter karsey
        form.base_fields['category'].queryset = Category.objects.all()
        return form
