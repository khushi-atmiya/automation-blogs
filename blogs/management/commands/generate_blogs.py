import requests
import feedparser
import random
import urllib.parse
import time
import re
import json
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from ddgs import DDGS

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from blogs.models import MainCategory, Category, BlogPost


class Command(BaseCommand):
    help = 'Auto Blog Generator — Pollinations.ai (No API Key Required)'
       # ------------------------------------------------------------------ #
    #  Helper: call Pollinations text API with retry                       #
    # ------------------------------------------------------------------ #
    def _pollinations_text(self, prompt, retries=4, timeout=150):
        """Call Google Gemini API (100% Free and Highly Reliable)."""
        import os
        api_key = os.environ.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        for attempt in range(1, retries + 1):
            self.stdout.write(f"  [Gemini API] Attempt {attempt}/{retries}...")
            
            try:
                res = requests.post(url, headers=headers, json=data, timeout=timeout)
                
                if res.status_code == 200:
                    json_data = res.json()
                    # Google Gemini JSON structure
                    text = json_data['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    # Clean AI thinking and metadata
                    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'```(?:json|html|markdown|text)?\n?', '', text, flags=re.IGNORECASE)
                    text = text.replace('```', '')
                    
                    if text.strip():
                        return text.strip()
                    self.stdout.write(self.style.WARNING("  empty response, retrying..."))
                elif res.status_code == 429:
                    wait_time = 20 * attempt
                    self.stdout.write(self.style.ERROR(f"  [!] Rate Limit (429), Google is strict on 15 requests/min. Waiting {wait_time}s..."))
                    import time
                    time.sleep(wait_time)
                    continue
                elif res.status_code == 503:
                    wait_time = 30 * attempt
                    self.stdout.write(self.style.ERROR(f"  [!] Server Busy (503), high demand on free tier. Waiting {wait_time}s..."))
                    import time
                    time.sleep(wait_time)
                    continue
                else:
                    self.stdout.write(self.style.WARNING(f"  HTTP {res.status_code}: {res.text[:100]}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Error: {e}, retrying..."))
            
            if attempt < retries:
                wait_time = 15 * attempt
                self.stdout.write(self.style.WARNING(f"  Standard wait {wait_time}s before retry..."))
                import time
                time.sleep(wait_time)
                
        return ""

    def _generate_title(self, trends, region, cat_name):
        """Generate a clean, specific blog title using a minimal prompt."""
        # Pick the single most informative trend headline as base
        first_trend = ""
        for line in trends.split("\n"):
            clean = line.replace("- ", "").strip()
            if len(clean.split()) >= 4:
                first_trend = clean
                break

        # Very short prompt — avoids triggering Pollinations' chain-of-thought
        title_prompt = (
            f"Write ONE blog post title (8 to 11 words) about this news story: {first_trend}. "
            f"Make it engaging and professional. Output ONLY the title text, nothing else."
        )
        raw = self._pollinations_text(title_prompt, retries=3, timeout=45)

        if raw:
            # Take the very first non-empty line only
            for line in raw.split("\n"):
                candidate = line.strip()
                # Skip lines that look like thinking/reasoning
                if len(candidate.split()) < 4:
                    continue
                if any(bad in candidate.lower() for bad in [
                    'okay', 'let me', "i'll", "i need", "let's", 'so i', 'we need',
                    'count:', 'words:', 'rules:', 'note:', 'sure,', 'here is',
                    'here\'s', 'the title', 'title is', 'generate', 'write a'
                ]):
                    continue
                # Clean punctuation artifacts
                candidate = re.sub(r'^[\*\'"#\-]+', '', candidate)
                candidate = re.sub(r'[\*\'"#]+$', '', candidate)
                candidate = candidate.strip()
                if len(candidate.split()) >= 4:
                    return candidate

        # Fallback: use the raw first trend headline (already real & specific)
        if first_trend:
            return first_trend[:100]
        return f"{cat_name} Latest News and Updates"

    # ------------------------------------------------------------------ #
    #  Main handle                                                         #
    # ------------------------------------------------------------------ #
    def handle(self, *args, **kwargs):
        categories = Category.objects.filter(main_categories__isnull=False).distinct()
        if not categories:
            self.stdout.write(self.style.ERROR('No categories with domain access found'))
            return

        def is_duplicate(title):
            return BlogPost.objects.filter(title__iexact=title).exists()

        for cat in categories:
            associated_mains = cat.main_categories.all()
            main_cat_names = [mc.name for mc in associated_mains]
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Generating for category: {cat.name} (Assigned to: {', '.join(main_cat_names)})")
            self.stdout.write('='*60)

            # -------------------------------------------------------- #
            # 1. Fetch RSS trends (US or UK)                            #
            # -------------------------------------------------------- #
            query = urllib.parse.quote(cat.name)
            target_region = random.choice(["US", "UK"])

            if target_region == "US":
                rss_url = (
                    f"https://news.google.com/rss/search?q={query}"
                    f"+when:7d&hl=en-US&gl=US&ceid=US:en"
                )
            else:
                rss_url = (
                    f"https://news.google.com/rss/search?q={query}"
                    f"+when:7d&hl=en-GB&gl=GB&ceid=GB:en"
                )

            feed = feedparser.parse(rss_url)
            trends = ""
            if feed.entries:
                trends = "\n".join([f"- {e.title}" for e in feed.entries[:5]])
                self.stdout.write(f"RSS trends fetched ({len(feed.entries)} items)")
            else:
                trends = cat.name
                self.stdout.write(self.style.WARNING("No RSS results, using category name"))

            # -------------------------------------------------------- #
            # 2. Generate TITLE first (before body)                     #
            # -------------------------------------------------------- #
            self.stdout.write("Generating title...")
            title = self._generate_title(trends, target_region, cat.name)

            # Handle duplicate title
            if is_duplicate(title):
                title = f"{title} {random.randint(100, 999)}"

            safe_title = title.encode('ascii', 'replace').decode('ascii')
            self.stdout.write(self.style.SUCCESS(f"Title: {safe_title}"))

            # -------------------------------------------------------- #
            # 3. Build the main prompt using a Senior Journalist persona
            # -------------------------------------------------------- #
            persona = (
                "You are a world-class Senior Investigative Journalist and Industry Analyst with 20+ years of experience "
                "writing for The Economist, Wired, and Financial Times. Your writing is sophisticated, deeply informative, "
                "and completely indistinguishable from high-end human journalism."
            )
            
            main_prompt = (
                f"{persona}\n\n"
                f"Write a comprehensive, highly monetizable, and deeply analytical blog post titled '{title}'.\n\n"
                f"CORE TOPICS TO COVER:\n{trends}\n\n"
                f"FOCUS AREAS:\n"
                f"- CATEGORY: Deeply focus on the core category '{cat.name}'. Ensure this topic is the absolute central theme.\n"
                f"- LOCATION CONTEXT: {target_region} (Heavily focus on {target_region} specifically, including {target_region} local impact, {target_region} regulations, and {target_region} market trends).\n"
                f"- HIGH CPM KEYWORDS: Naturally integrate high CPM (Cost Per Mille) and high CPC keywords relevant to '{cat.name}' in the {target_region} market (e.g., enterprise solutions, finance, insurance, specialized services, B2B).\n\n"
                f"STRICT REQUIREMENTS:\n"
                f"1. LENGTH: Target exactly 1200 to 1300 words of pure substance. No filler.\n"
                f"2. TONE: Professional, authoritative, and engaging. Avoid all AI clichés (No 'Firstly', 'In conclusion', 'Unlock your potential').\n"
                f"3. STRUCTURE: Start with a powerful narrative hook. Use deep-dive analysis, expert-style insights, and future-looking predictions.\n"
                f"4. PARAGRAPHS: Write exactly 12-14 detailed paragraphs (around 90-100 words each).\n"
                f"5. NO META-TALK: Do not say 'Certainly', 'Here is the blog', or mention being an AI. Output ONLY the blog body text.\n"
                f"6. FORMATTING: Use clear paragraph breaks. You may use markdown headers (##) for sections."
            )

            # -------------------------------------------------------- #
            # 4. Get main content from Pollinations.ai                  #
            # -------------------------------------------------------- #
            self.stdout.write("Calling Pollinations.ai for blog body...")
            content_text = self._pollinations_text(main_prompt, retries=4, timeout=150)

            if content_text:
                self.stdout.write(self.style.SUCCESS(f"Got response: {len(content_text.split())} words"))
            else:
                self.stdout.write(self.style.ERROR("Pollinations failed to return content. Skipping."))
                continue

            # -------------------------------------------------------- #
            # 5. If short, accumulate extra sections
            # -------------------------------------------------------- #
            WORD_TARGET = 1250
            total_words = len(content_text.split())

            if total_words < WORD_TARGET:
                self.stdout.write(self.style.WARNING(f"Only {total_words} words. Boosting to {WORD_TARGET}..."))
                extra_parts = [content_text]

                for boost in range(1, 6):
                    if total_words >= WORD_TARGET:
                        break
                    self.stdout.write(f"  Expansion phase {boost}...")
                    
                    # Use the last part of previous content to maintain flow
                    context_snippet = " ".join(extra_parts[-1].split()[-100:])
                    
                    extra_prompt = (
                        f"{persona}\n\n"
                        f"Continue the highly monetizable analysis for the blog post titled '{title}' with a heavy focus on the '{cat.name}' category in the {target_region}.\n"
                        f"The previous section ended with: '...{context_snippet}'\n\n"
                        f"Write 3 more high-value paragraphs (expanding on {target_region} specific data points and high CPM keywords relevant to {cat.name}).\n"
                        f"Maintain the sophisticated, human-like journalistic tone. Output body text only."
                    )
                    extra = self._pollinations_text(extra_prompt, retries=2, timeout=120)
                    if extra and len(extra.split()) > 80:
                        extra_parts.append(extra)
                        total_words += len(extra.split())
                        self.stdout.write(self.style.WARNING(f"  Current total: {total_words} words"))

                content_text = "\n\n".join(extra_parts)
                self.stdout.write(self.style.SUCCESS(f"Final word count: {len(content_text.split())}"))

            if len(content_text.split()) < 600:
                self.stdout.write(self.style.ERROR("Too short after boosts. Skipping."))
                continue

            # body_text is the full content (title already separate)
            body_text = content_text

            # -------------------------------------------------------- #
            # 6. Parse paragraphs and build Premium HTML
            # -------------------------------------------------------- #
            # Remove common AI meta-talk/prefixes
            body_text = re.sub(r'^(Certainly|Sure|Here is|Okay|Absolutely|Based on).*?:\s*', '', body_text, flags=re.IGNORECASE | re.DOTALL)
            
            raw_lines = body_text.split("\n")
            
            p_style = (
                "margin-bottom: 24px; "
                "font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; "
                "font-size: 17px; "
                "line-height: 2.0; "
                "color: #1a1a1a; "
                "text-align: justify; "
                "letter-spacing: -0.01em;"
            )
            h2_style = (
                "margin-top: 45px; "
                "margin-bottom: 20px; "
                "font-family: 'Inter', system-ui, sans-serif; "
                "font-size: 28px; "
                "font-weight: 700; "
                "color: #2d3436; "
                "line-height: 1.3;"
            )
            strong_style = "color: #0984e3; font-weight: 600;"

            description = []
            p_count = 0
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                
                # HEAVY FILTER: Discard any paragraph with JSON, code, or meta-talk signatures
                junk_signals = [
                    '"role":', '"content":', '"reasoning_content":', '```', 
                    'Tool calls:', 'assistant', 'prompt', 'paragraph', 'word count',
                    'Here is', 'Certainly', 'Absolutely', '{"', '}"'
                ]
                # If it has more than 2 technical symbols or starts with {
                if line.startswith('{') or line.count('{') > 1 or line.count('"') > 8:
                    if any(js in line for js in junk_signals):
                        continue
                
                if any(js in line.lower() for js in ['word count', 'paragraphs:', 'here is']):
                    if len(line.split()) < 40: # Meta-talk is usually short
                        continue
                    
                # Detect and format headings
                if line.startswith('##') or (line.isupper() and len(line.split()) < 8) or line.endswith(':'):
                    clean_h = re.sub(r'^#+\s*', '', line).strip(':').strip()
                    if 3 < len(clean_h.split()) < 12:
                        description.append(f'<h2 style="{h2_style}">{clean_h}</h2>')
                    continue

                words = line.split()
                if len(words) < 30:
                    continue

                # Highlight key business/tech phrases instead of random words
                keywords = ['innovation', 'market', 'growth', 'strategy', 'digital', 'ecosystem', 'investment', 'technology', 'sustainable', 'intelligence', 'frontier', 'global', 'leadership']
                highlighted_line = line
                
                found_keywords = [w for w in words if w.lower().strip(',.()') in keywords]
                if found_keywords:
                    to_highlight = random.sample(found_keywords, min(2, len(found_keywords)))
                    for kw in to_highlight:
                        highlighted_line = highlighted_line.replace(f" {kw} ", f' <strong style="{strong_style}">{kw}</strong> ')

                p_html = f'<p style="{p_style}">{highlighted_line}</p>'
                description.append(p_html)
                p_count += 1

            # If no headings were generated, inject one in the middle for structure
            if not any('<h2' in d for d in description) and len(description) > 6:
                mid = len(description) // 2
                description.insert(mid, f'<h2 style="{h2_style}">Strategic Insights and Market Outlook</h2>')

            if len(description) < 5:
                self.stdout.write(self.style.WARNING("Too few paragraphs after parsing. Skipping."))
                continue

            self.stdout.write(f"Paragraphs built: {len(description)}")

            # -------------------------------------------------------- #
            # 7. Generate image via Bing Images (Migrated from test-image.py)
            # -------------------------------------------------------- #
            slug = slugify(title) + "-" + str(random.randint(1000, 9999))

            blog = BlogPost(
                category=cat,
                title=title,
                slug=slug,
                description=description,
            )

            clean_title = re.sub(r'<[^>]*>?', '', title)
            search_query = f"high quality blog cover {cat.name} {clean_title}"
            
            self.stdout.write(f"Searching Images for: \"{search_query}\"...")
            
            image_saved = False
            try:
                # Search for images using DuckDuckGo
                results = []
                with DDGS() as ddgs:
                    # Extract the first few image results as fallbacks
                    for r in ddgs.images(search_query, max_results=5):
                        results.append(r)
                    
                if not results:
                    raise Exception('No images found from search.')
                    
                image = None
                for result in results:
                    image_url = result['image']
                    self.stdout.write(f'  [ImageGen] Trying image URL: {image_url}')
                    
                    # Download the image with browser headers to prevent Forbidden errors
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                    }
                    
                    try:
                        response = requests.get(image_url, headers=headers, stream=True, timeout=15)
                        response.raise_for_status()
                        
                        # Load image into Pillow
                        image = Image.open(BytesIO(response.content))
                        break # Successfully downloaded, exit loop
                    except Exception as dl_err:
                        self.stdout.write(self.style.WARNING(f'  [ImageGen] Failed to download {image_url}: {dl_err}'))
                        continue
                        
                if not image:
                    raise Exception('Failed to download any images from the search results.')
                
                # Convert to RGB if it has an alpha channel (like PNG) or is in another mode
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                    
                # ---------------------------------------------------------
                # Mimic the 'sharp' resize with { fit: 'cover', position: 'center' }
                # ---------------------------------------------------------
                target_width = 1280
                target_height = 720
                
                img_ratio = image.width / image.height
                target_ratio = target_width / target_height
                
                if img_ratio > target_ratio:
                    # Image is wider than the target ratio - crop the sides
                    new_width = int(target_ratio * image.height)
                    offset = (image.width - new_width) / 2
                    crop_box = (offset, 0, image.width - offset, image.height)
                else:
                    # Image is taller than the target ratio - crop the top and bottom
                    new_height = int(image.width / target_ratio)
                    offset = (image.height - new_height) / 2
                    crop_box = (0, offset, image.width, image.height - offset)
                    
                # Perform the center crop
                image = image.crop(crop_box)
                
                # Resize to final dimensions using high-quality Lanczos resampling
                image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                buffer_io = BytesIO()
                image.save(buffer_io, format='JPEG', quality=85)
                imageBuffer = buffer_io.getvalue()
                
                blog.image.save(f"{slug}.jpg", ContentFile(imageBuffer), save=False)
                self.stdout.write(self.style.SUCCESS("✅ Image successfully downloaded, processed and saved!"))
                image_saved = True
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Image error: {e}"))

            if not image_saved:
                self.stdout.write(self.style.WARNING("No image saved, posting without image."))

            # -------------------------------------------------------- #
            # 8. Save blog to database                                  #
            # -------------------------------------------------------- #
            blog.save()
            blog.main_categories.set(associated_mains)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Blog created: \"{safe_title}\" ({len(content_text.split())} words, "
                    f"{len(description)} paragraphs)"
                )
            )
            
            # Rate limit pacing: Wait 10 seconds before generating the next blog
            # to stay comfortably below Google's 15 requests/minute free tier limit.
            self.stdout.write(self.style.WARNING("Waiting 10 seconds before starting the next blog to avoid rate limits..."))
            import time
            time.sleep(10)
