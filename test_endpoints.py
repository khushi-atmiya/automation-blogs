import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blogsBackend.settings')
django.setup()

from blogs.models import BlogPost, MainCategory

def test_rendering():
    c = Client()
    
    # 1. Fetch domain names and a sample blog post from the database
    domains = [mc.name for mc in MainCategory.objects.all()]
    print(f"--- Available Domains in DB: {domains} ---")
    
    if not domains:
        print("No domains (MainCategories) found in database. Creating a mock domain...")
        mc = MainCategory.objects.create(name='urbanloanhub.store')
        domains = [mc.name]
        
    domain = domains[0]
    
    # Fetch posts for this domain
    posts = BlogPost.objects.filter(main_category__name__iexact=domain)
    print(f"--- Found {posts.count()} posts for domain '{domain}' ---")
    
    if not posts.exists():
        print(f"Creating a mock post for '{domain}' to test detail view...")
        from blogs.models import Category
        cat, _ = Category.objects.get_or_create(name='technology')
        mc = MainCategory.objects.get(name__iexact=domain)
        post = BlogPost.objects.create(
            main_category=mc,
            category=cat,
            title='Test Blog Post on ' + domain,
            slug='test-blog-post-on-domain',
            description='<p>This is a test blog post description on the dynamic rendering engine.</p>',
            author='Test Agent',
            blog_date=datetime.date.today() if 'datetime' in globals() else None
        )
    else:
        post = posts.first()
        
    print(f"Using test blog post slug: '{post.slug}' for domain: '{domain}'")
    
    # 2. Test robots.txt rendering
    print("\n================ ROBOTS.TXT OUTPUT ================")
    response = c.get('/robots.txt', HTTP_HOST=domain)
    print(response.content.decode('utf-8'))
    
    # 3. Test sitemap.xml rendering
    print("\n================ SITEMAP.XML OUTPUT ================")
    response = c.get('/sitemap.xml', HTTP_HOST=domain)
    sitemap_content = response.content.decode('utf-8')
    print(sitemap_content[:500] + "\n... [truncated] ...\n" + sitemap_content[-100:])
    
    # 4. Test blog detail HTML rendering
    print(f"\n================ BLOG DETAIL HTML VIEW (/{post.slug}/) ================")
    response = c.get(f'/blog/{post.slug}/', HTTP_HOST=domain)
    html_content = response.content.decode('utf-8')
    
    # Print the start of the HTML to verify structure, metadata, and CSS
    print(html_content[:1500] + "\n... [truncated body content] ...\n" + html_content[-600:])
    
    # Write the output HTML to a file in scratch folder so it can be previewed
    scratch_dir = r"C:\Users\Atmiya 500\.gemini\antigravity-ide\scratch"
    os.makedirs(scratch_dir, exist_ok=True)
    html_file = os.path.join(scratch_dir, f"rendered_blog_{post.slug}.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\nSaved full HTML output to: {html_file}")

if __name__ == '__main__':
    test_rendering()
