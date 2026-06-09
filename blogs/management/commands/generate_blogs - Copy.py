import os
import requests
import feedparser
import json
import random
import urllib.parse
import time
import re
import hashlib
import base64

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from blogs.models import MainCategory, Category, BlogPost


class Command(BaseCommand):
    help = 'Ultimate AI Auto Blog Generator (Stable + SEO + Long Content)'

    def handle(self, *args, **kwargs):
        main_categories = MainCategory.objects.all()

        if not main_categories:
            self.stdout.write(self.style.ERROR('No main categories found'))
            return

        # 🔥 CHANGED: validation relaxed (for combining)
        def is_valid_content(text):
            return len(text.split()) >= 600

        def is_duplicate(title):
            return BlogPost.objects.filter(title__iexact=title).exists()

        for main_cat in main_categories:
            print("main_cat",main_cat)
            for cat in main_cat.categories.all():
                print("cat",cat)
                self.stdout.write(f"\nGenerating: {main_cat.name} -> {cat.name}")

                # RSS Trends: Authentic US/UK region search without explicitly appending text
                query = urllib.parse.quote(cat.name)
                
                # Randomly pick US or UK for this specific blog
                target_region = random.choice(["US", "UK"])
                
                if target_region == "US":
                    rss_url = f"https://news.google.com/rss/search?q={query}+when:7d&hl=en-US&gl=US&ceid=US:en"
                else:
                    rss_url = f"https://news.google.com/rss/search?q={query}+when:7d&hl=en-GB&gl=GB&ceid=GB:en"
                    
                feed = feedparser.parse(rss_url)

                trends = ""
                if feed.entries:
                    trends = "\n".join([f"- {e.title}" for e in feed.entries[:3]])

                # DYNAMIC PROMPT for region
                prompt = (
                    f"Write an extremely detailed, 1500-word professional blog post about: {trends}. \n\n"
                    f"Focus specifically on {target_region} trends and context. Start with 'TITLE:' then the title (the title MUST be exactly 7 or 8 words long). "
                    "Then write at least 12 long paragraphs. Return only the blog text."
                )

                content_text = ""
                
                # 🔥 POLLINATIONS INTEGRATION (TEXT)
                self.stdout.write("Generating text with Pollinations.ai (OpenAI model)...")
                poll_url = "https://text.pollinations.ai/"
                # headers = {
                #     "Authorization": "Bearer sk_OXQA56dQbKwsCpipHbcxTgqFuPFtdg6S",
                #     "Content-Type": "application/json"
                # }
                payload = {
                    "model": "openai",
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                try:
                    res = requests.post(poll_url, json=payload, timeout=120)
                    if res.status_code == 200:
                        data = res.json()
                        temp_text = data['choices'][0]['message']['content']
                        if is_valid_content(temp_text):
                            content_text = temp_text
                            self.stdout.write(self.style.SUCCESS("Pollinations Text Success!"))
                        else:
                            self.stdout.write(self.style.WARNING("Pollinations Text was too short."))
                    else:
                        self.stdout.write(self.style.WARNING(f"Pollinations failed ({res.status_code}): {res.text[:100]}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Pollinations error: {e}"))

                if not content_text:
                    self.stdout.write(self.style.ERROR("Failed after retries"))
                    continue

                # Extract title
                lines = content_text.split("\n")
                title = f"{cat.name} Trends {random.randint(1000,9999)}"
                body_text = content_text

                for i, line in enumerate(lines[:6]):
                    if "TITLE:" in line.upper():
                        title = line.split("TITLE:")[1].strip().replace("*", "").replace('"', '')
                        body_text = "\n".join(lines[i+1:])
                        break

                if is_duplicate(title):
                    title += f" {random.randint(1000,9999)}"

                # Paragraph split
                raw_paragraphs = re.split(r'\n\s*\n', body_text)

                paragraphs = []
                for p in raw_paragraphs:
                    p = p.strip()
                    if len(p.split()) < 50:
                        continue
                    paragraphs.append(p)

                # Styles (UNCHANGED FORMAT)
                p_style = "margin-bottom: 20px; font-family: 'Inter', system-ui, -apple-system, sans-serif; font-size: 16px; line-height: 1.8; color: #2d3436; text-align: justify;"
                strong_style = "color: #0984e3;"

                description = []
                for p in paragraphs:
                    words = p.split()
                    for _ in range(min(3, len(words)//60)):
                        try:
                            idx = random.randint(5, len(words)-5)
                            words[idx] = f'<strong style="{strong_style}">{words[idx]}</strong>'
                        except: pass

                    p_html = f'<p style="{p_style}">{" ".join(words)}</p>'
                    description.append(p_html)

                if len(description) < 6:
                    self.stdout.write(self.style.WARNING("Skipped (too short)"))
                    continue

                # Image Style Logic (Realistic vs Infographic)
                is_guide = any(word in title.lower() for word in ['how to', 'guide', 'steps', 'tips', 'resume', 'applying', 'scams', 'scam'])
                if is_guide:
                    style_prompt = "clean vector infographic, professional instructional design, educational layout, structured, clear text elements, bright colors"
                else:
                    style_prompt = "photorealistic office or laboratory environment, high-tech, cinematic lighting, professional photography, hyper-realistic, depth of field"
                
                negative_instructions = "IMPORTANT: NO recognizable politicians, NO real-world celebrities, NO specific public figures. Use only generic, anonymous human professionals, or abstract 3D elements."
                image_query = f"Professional blog header background for: {title}. {style_prompt}. {negative_instructions} High-quality composition, clean design, editorial style."

                
                blog = BlogPost(
                    main_category=main_cat,
                    category=cat,
                    title=title,
                    slug=slugify(title) + "-" + str(random.randint(1000,9999)),
                    description=description
                )

                # --- IMAGE GENERATION (POLLINATIONS) ---
                self.stdout.write("Generating Image with Pollinations.ai...")
                poll_img_url = f"https://image.pollinations.ai/image/{urllib.parse.quote(image_query)}"
                # headers = {
                #     "Authorization": "Bearer sk_OXQA56dQbKwsCpipHbcxTgqFuPFtdg6S"
                # }
                for img_attempt in range(3):
                    try:
                        img_res = requests.get(poll_img_url, headers=headers, timeout=60)
                        if img_res.status_code == 200:
                            blog.image.save(f"{blog.slug}.jpg", ContentFile(img_res.content), save=False)
                            self.stdout.write(self.style.SUCCESS("Pollinations Image Success!"))
                            break
                        else:
                            self.stdout.write(self.style.WARNING(f"Pollinations Image fallback {img_attempt+1} ({img_res.status_code})"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Pollinations Image error: {e}"))
                        time.sleep(5)

                blog.save()
                self.stdout.write(self.style.SUCCESS(f"Created: {title}"))
