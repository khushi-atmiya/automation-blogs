import requests
import feedparser
import random
import urllib.parse
import time
import re

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from blogs.models import MainCategory, Category, BlogPost


class Command(BaseCommand):
    help = 'Auto Blog Generator — Pollinations.ai (No API Key Required)'
   
       # ------------------------------------------------------------------ #
    #  Helper: call Pollinations text API with retry                       #
    # ------------------------------------------------------------------ #
    def _pollinations_text(self, prompt, retries=3, timeout=120):
        """Call Pollinations.ai text endpoint and return clean text."""
        encoded = urllib.parse.quote(prompt)
        url = f"https://text.pollinations.ai/{encoded}?seed={random.randint(1, 99999)}&model=openai"
        for attempt in range(1, retries + 1):
            self.stdout.write(f"  [Pollinations] Attempt {attempt}/{retries}...")
            try:
                res = requests.get(url, timeout=timeout)
                if res.status_code == 200:
                    text = res.text.strip()
                    
                    # 1. Try to find the "content" value if it's a JSON string
                    # Often Pollinations/models return the full JSON object as a string
                    if '"content":' in text and '"role":' in text:
                        try:
                            import json
                            # Search for the start of the JSON object
                            json_start = text.find('{')
                            json_end = text.rfind('}')
                            if json_start != -1 and json_end != -1:
                                potential_json = text[json_start:json_end+1]
                                data = json.loads(potential_json)
                                if isinstance(data, dict):
                                    text = data.get("content", data.get("text", text))
                        except Exception:
                            # If JSON fails, try regex extraction for "content": "..."
                            content_match = re.search(r'"content":\s*"(.*?)"', text, re.DOTALL)
                            if content_match:
                                text = content_match.group(1).encode().decode('unicode_escape')
                    
                    # 2. Clean AI thinking and metadata
                    text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'```json.*?```', '', text, flags=re.DOTALL)
                    # Strip any lingering leading/trailing JSON markers
                    text = re.sub(r'^\{.*?"content":\s*', '', text, flags=re.DOTALL)
                    text = re.sub(r'\s+,"role":.*\}$', '', text, flags=re.DOTALL)
                    
                    if text.strip():
                        return text.strip()
                    self.stdout.write(self.style.WARNING("  empty response, retrying..."))
                else:
                    self.stdout.write(self.style.WARNING(f"  HTTP {res.status_code}, retrying..."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Error: {e}, retrying..."))
            time.sleep(3)
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

                self.stdout.write(self.style.SUCCESS(f"Title: {title}"))

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
                    f"Write a comprehensive, professional, and deeply analytical blog post titled '{title}'.\n\n"
                    f"CORE TOPICS TO COVER:\n{trends}\n\n"
                    f"LOCATION CONTEXT: {target_region} (Focus on local impact, regional data, and {target_region} business trends).\n\n"
                    f"STRICT REQUIREMENTS:\n"
                    f"1. LENGTH: Minimum 1600 words of substance. No filler.\n"
                    f"2. TONE: Professional, authoritative, and engaging. Avoid all AI clichés (No 'Firstly', 'In conclusion', 'It is important to note', 'Unlock your potential').\n"
                    f"3. STRUCTURE: Start with a powerful narrative hook. Use deep-dive analysis, expert-style insights, and future-looking predictions.\n"
                    f"4. PARAGRAPHS: Write at least 15-18 long, detailed paragraphs (minimum 120 words each).\n"
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
                WORD_TARGET = 1600
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
                            f"Continue the analysis for the blog post titled '{title}'.\n"
                            f"The previous section ended with: '...{context_snippet}'\n\n"
                            f"Write 4 more massive, high-value paragraphs (150+ words each) expanding on specific data points, "
                            f"global implications, and technical deep-dives related to {cat.name} in the {target_region}.\n"
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
                # 7. Generate image via Pollinations.ai                     #
                # -------------------------------------------------------- #
                is_guide = any(
                    kw in title.lower()
                    for kw in ['how to', 'guide', 'steps', 'tips', 'resume', 'applying', 'scam', 'scams']
                )
                if is_guide:
                    style_prompt = (
                        "clean vector infographic, professional instructional design, "
                        "educational layout, structured, bright colors, modern flat design"
                    )
                else:
                    style_prompt = (
                        "photorealistic office or laboratory environment, high-tech workspace, "
                        "cinematic lighting, professional photography, hyper-realistic, depth of field"
                    )

                safety_note = (
                    "NO real politicians, NO celebrities, NO public figures. "
                    "Only anonymous professionals or abstract 3D elements."
                )
                image_query = (
                    f"Professional editorial blog header image for: {title}. "
                    f"{style_prompt}. {safety_note} "
                    f"High-quality, clean composition, magazine-style."
                )

                slug = slugify(title) + "-" + str(random.randint(1000, 9999))

                blog = BlogPost(
                    category=cat,
                    title=title,
                    slug=slug,
                    description=description,
                )

                self.stdout.write("Generating image with Pollinations.ai...")
                img_url = (
                    f"https://image.pollinations.ai/prompt/"
                    f"{urllib.parse.quote(image_query)}"
                    f"?width=1280&height=720&model=flux&nologo=true"
                )
                image_saved = False
                for img_attempt in range(3):
                    try:
                        img_res = requests.get(img_url, timeout=60)
                        if img_res.status_code == 200 and img_res.content:
                            blog.image.save(f"{slug}.jpg", ContentFile(img_res.content), save=False)
                            self.stdout.write(self.style.SUCCESS("Image saved!"))
                            image_saved = True
                            break
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"Image attempt {img_attempt+1} failed ({img_res.status_code})")
                            )
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Image error: {e}"))
                    time.sleep(4)

                if not image_saved:
                    self.stdout.write(self.style.WARNING("No image saved, posting without image."))

                # -------------------------------------------------------- #
                # 8. Save blog to database                                  #
                # -------------------------------------------------------- #
                blog.save()
                blog.main_categories.set(associated_mains)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Blog created: \"{title}\" ({len(content_text.split())} words, "
                        f"{len(description)} paragraphs)"
                    )
                )
