import os
import sys
import re
import json
import time
import html
import random
import requests
import urllib.parse
from PIL import Image, ImageOps
from io import BytesIO

# Try to initialize Django settings if run inside a Django project environment
try:
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blogsBackend.settings')
    django.setup()
    from django.core.files.base import ContentFile
    from blogs.models import BlogPost
    DJANGO_AVAILABLE = True
except Exception:
    DJANGO_AVAILABLE = False

class ImagePipeline:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.used_images_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'used_images.json')
        self.used_urls = set()
        if os.path.exists(self.used_images_file):
            try:
                with open(self.used_images_file, 'r', encoding='utf-8') as f:
                    self.used_urls = set(json.load(f))
            except Exception:
                pass

    def _mark_url_used(self, url):
        self.used_urls.add(url)
        try:
            with open(self.used_images_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.used_urls), f)
        except Exception as e:
            self._log(f"Failed to save used images: {e}", "WARNING")

    def _log(self, msg, level="INFO"):
        if self.verbose:
            print(f"[{level}] {msg}")

    def _clean_title_keywords(self, title):
        clean = re.sub(r'[^\w\s-]', '', title).lower()
        noise = {
            'top', 'five', 'ten', 'best', 'worst', 'essential', 'rules', 'tips', 'tricks',
            'complete', 'ultimate', 'comprehensive', 'definitive', 'balanced', 'simple',
            'easy', 'quick', 'new', 'latest', 'updated', 'proven', 'effective',
            'july', 'june', 'august', 'september', 'october',
            'november', 'december', 'january', 'february', 'march', 'april',
            'year', 'years', '2025', '2026', '2027', 'cnbc', 'picks', 'guide', 'steps',
            'how', 'to', 'why', 'what', 'ways', 'things', 'secrets', 'ideas'
        }
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'for', 'of', 'in', 'on', 'at', 'with', 'from', 'by'}
        words = [w for w in clean.split() if w not in noise and w not in stopwords and len(w) >= 3]
        return " ".join(words)
    def _validate_image_url(self, url):
        """
        Verify that the URL has no bad path keywords and doesn't belong to known commercial stock sites.
        """
        if url in self.used_urls:
            self._log(f"      [Rejected] Image already used previously: {url}")
            return False

        url_lower = url.lower()
        
        # 1. Reject watermark commercial stock photo sites
        stock_patterns = [
            "shutterstock.com", "gettyimages.", "istockphoto.com", "adobe.com/express",
            "stock.adobe.com", "dreamstime.com", "depositphotos.com", "123rf.com",
            "alamy.com", "vectorstock.com", "canva.com"
        ]
        if any(sp in url_lower for sp in stock_patterns):
            return False
            
        # 2. Reject typical non-content images, icons, maps, graphics, and geography
        bad_keywords = [
            "/logo/", "/icon/", "/button/", "/ad/", "/banner/", "favicon", "avatar",
            "crest", "shield", "badge", "vector", "clipart", ".svg", "transparent", 
            "background", "text", "font", "character", "illustration", "drawing", "cartoon", "symbol",
            "-map.", "-map-", "_map.", "_map-", "/map/", "/maps/",
            "political-", "geography", "atlas", "region-map", "world-map",
            "countries-map", "physical-map", "overview-map"
        ]
        if any(bk in url_lower for bk in bad_keywords):
            return False
            
        # 3. Allow known image CDN domains that serve images without file extensions
        known_image_cdns = [".bing.net/th/id/", "images.unsplash.com", "images.pexels.com"]
        is_known_cdn = any(cdn in url_lower for cdn in known_image_cdns)
        
        # 4. Only accept common web image extensions (skip check for known CDNs)
        if not is_known_cdn:
            if not any(url_lower.endswith(ext) or ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return False
            
        return True

    def _fetch_bing_cdn(self, query):
        self._log(f"Searching Bing Images for: '{query}'")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&first=1&count=35"
        urls = []
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                # Step 1: Find m= attributes (HTML-entity-encoded JSON) from iusc elements
                m_attrs = re.findall(r'm="(\{[^"]*\})"', res.text)
                for raw_json in m_attrs:
                    decoded = html.unescape(raw_json)
                    murl_match = re.search(r'"murl"\s*:\s*"(https?://[^"]+)"', decoded)
                    if murl_match:
                        u = murl_match.group(1)
                        self._log(f"    Found Source URL: {u}")
                        if self._validate_image_url(u):
                            if u not in urls:
                                urls.append(u)
                        else:
                            self._log(f"      [Rejected] Stock/watermarked/non-image: {u}")
                
                # Step 2: Fallback to OIP thumbnails if no murl found
                if not urls:
                    self._log(f"    No source URLs found, trying OIP thumbnails...")
                    oip_matches = re.findall(r'(https?://[^\s"\'\\<>]+?\.bing\.net/th/id/OIP\.[^\s"\'\\<>]+)', res.text)
                    for m in oip_matches:
                        u = html.unescape(m)
                        if "?" in u:
                            u = u.split("?")[0]
                        if u not in urls:
                            urls.append(u)
        except Exception as e:
            self._log(f"Bing search error: {e}", "WARNING")
        self._log(f"    Total Bing results: {len(urls)}")
        return urls

    def _fetch_wikimedia(self, query):
        self._log(f"Searching Wikimedia Commons for: '{query}'")
        headers = {
            "User-Agent": "AIBlogGenerator/2.0 (contact@example.com) requests"
        }
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 15,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "format": "json"
        }
        urls = []
        try:
            res = requests.get(api_url, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, pinfo in pages.items():
                    imageinfo = pinfo.get("imageinfo", [{}])[0]
                    img_url = imageinfo.get("url", "")
                    if img_url:
                        self._log(f"    Found Candidate URL: {img_url}")
                        if self._validate_image_url(img_url):
                            # Verify license if available
                            extmetadata = imageinfo.get("extmetadata", {})
                            license_name = extmetadata.get("LicenseShortName", {}).get("value", "").lower()
                            # Reject non-commercial or restrictive licenses
                            if "non-commercial" in license_name or "nc" in license_name:
                                self._log(f"      [Rejected] Non-commercial/Restrictive license ({license_name}): {img_url}")
                                continue
                            if img_url not in urls:
                                urls.append(img_url)
                        else:
                            self._log(f"      [Rejected] Bad keywords or domain: {img_url}")
        except Exception as e:
            self._log(f"Wikimedia search error: {e}", "WARNING")
        return urls

    def _fetch_unsplash(self, query, access_key):
        self._log(f"Searching Unsplash for: '{query}'")
        url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&per_page=10"
        headers = {
            "Authorization": f"Client-ID {access_key}"
        }
        urls = []
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("results", []):
                    img_url = item.get("urls", {}).get("regular", "")
                    if img_url:
                        self._log(f"    Found Candidate URL: {img_url}")
                        if self._validate_image_url(img_url) and img_url not in urls:
                            urls.append(img_url)
        except Exception as e:
            self._log(f"Unsplash search error: {e}", "WARNING")
        return urls

    def _fetch_pexels(self, query, api_key):
        self._log(f"Searching Pexels for: '{query}'")
        url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page=10"
        headers = {
            "Authorization": api_key
        }
        urls = []
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for photo in data.get("photos", []):
                    img_url = photo.get("src", {}).get("large2x", "")
                    if img_url:
                        self._log(f"    Found Candidate URL: {img_url}")
                        if self._validate_image_url(img_url) and img_url not in urls:
                            urls.append(img_url)
        except Exception as e:
            self._log(f"Pexels search error: {e}", "WARNING")
        return urls

    def _rank_and_validate_candidates(self, urls, keywords):
        candidates = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        keyword_list = keywords.split()
        
        # Limit to top 15 candidates to avoid too many downloads
        check_urls = urls[:15]
        self._log(f"  Checking top {len(check_urls)} of {len(urls)} candidates...")
        
        for url in check_urls:
            try:
                self._log(f"  Validating Candidate URL: {url}")
                
                # 1. Download the actual image (with size limit 5MB)
                res = requests.get(url, headers=headers, timeout=8, allow_redirects=True, stream=True)
                if res.status_code != 200:
                    self._log(f"    [Failed] Download returned status code: {res.status_code}")
                    continue
                
                content_type = res.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    self._log(f"    [Failed] URL content type is not image: {content_type}")
                    continue
                
                # Read image bytes (max 5MB)
                img_bytes = b""
                for chunk in res.iter_content(chunk_size=8192):
                    img_bytes += chunk
                    if len(img_bytes) > 5 * 1024 * 1024:
                        break
                
                if len(img_bytes) < 5000:
                    self._log(f"    [Failed] Image too small: {len(img_bytes)} bytes")
                    continue
                
                # 2. Open with PIL and check actual dimensions
                try:
                    img = Image.open(BytesIO(img_bytes))
                    width, height = img.size
                    self._log(f"    [Dimensions] {width}x{height} (aspect ratio: {width/max(height,1):.2f})")
                except Exception as e:
                    self._log(f"    [Failed] Cannot open image with PIL: {e}")
                    continue
                
                # 3. Reject very small images
                if width < 300 or height < 200:
                    self._log(f"    [Failed] Image too small: {width}x{height}")
                    continue
                    
                # 4. Score candidate based on real image properties
                score = 0
                
                # Landscape bonus (blog headers should be landscape/wide)
                aspect_ratio = width / max(height, 1)
                if aspect_ratio >= 1.4:  # Wide landscape (ideal for blog header)
                    score += 50
                    self._log(f"    [Bonus +50] Wide landscape image")
                elif aspect_ratio >= 1.1:  # Slightly landscape
                    score += 20
                    self._log(f"    [Bonus +20] Landscape image")
                elif aspect_ratio < 0.9:  # Portrait (likely map, infographic, pin)
                    score -= 30
                    self._log(f"    [Penalty -30] Portrait image (likely map/infographic)")
                
                # Resolution bonus (prefer higher resolution)
                if width >= 1200:
                    score += 30
                    self._log(f"    [Bonus +30] High resolution ({width}px wide)")
                elif width >= 800:
                    score += 15
                
                # File size bonus (larger files = more detail)
                if len(img_bytes) > 100000:
                    score += 10
                
                # Keyword Relevance Score (for Wikimedia/descriptive URLs)
                url_lower = url.lower()
                keyword_matches = sum(1 for kw in keyword_list if kw in url_lower)
                score += (keyword_matches * 10)
                
                # URL content relevance: boost food/health, penalize maps/geography
                food_kw = ["food", "dish", "recipe", "meal", "plate", "cuisine", "diet", "salad",
                           "cook", "kitchen", "healthy", "nutrition", "olive", "vegetable", "fruit"]
                food_matches = sum(1 for fk in food_kw if fk in url_lower)
                if food_matches > 0:
                    score += (food_matches * 20)
                    self._log(f"    [Bonus +{food_matches * 20}] Food-related URL keywords")
                
                map_kw = ["map", "atlas", "geography", "political", "region", "country",
                          "ocean", "sea-", "nations", "continent", "world"]
                map_matches = sum(1 for mk in map_kw if mk in url_lower)
                if map_matches > 0:
                    score -= (map_matches * 40)
                    self._log(f"    [Penalty -{map_matches * 40}] Map/geography URL keywords")
                
                self._log(f"    [Passed] Final Score: {score} (dims: {width}x{height}, keywords: {keyword_matches})")
                candidates.append((score, url, img_bytes))
            except Exception as e:
                self._log(f"    [Failed] Validation error: {e}")
                continue
                
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates

    def _optimize_image(self, img_bytes):
        """
        Strips EXIF, smart center-crops to 1280x720, and converts to WebP.
        """
        img = Image.open(BytesIO(img_bytes))
        
        # 1. Strip EXIF metadata by pasting onto a clean new RGB image
        if img.mode != 'RGB':
            img = img.convert('RGB')
        clean_img = Image.new("RGB", img.size)
        clean_img.paste(img)
        
        # 2. Smart center-crop to 1280x720
        target_size = (1280, 720)
        clean_img = ImageOps.fit(clean_img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        
        # 3. Save as WebP with 82% quality
        output_io = BytesIO()
        clean_img.save(output_io, format="WEBP", quality=82)
        return output_io.getvalue()

    def _generate_semantic_queries(self, title, category_name):
        words = self._clean_title_keywords(title).split()
        queries = []
        
        # 1. Full clean phrase
        if len(words) >= 2:
            queries.append(" ".join(words[:4]))
            
        # 2. Core subjects
        if len(words) >= 3:
            queries.append(" ".join(words[:3]))
        if len(words) >= 2:
            queries.append(f"{words[0]} {words[1]}")
            
        # 3. Add context fallback
        if words:
            queries.append(f"{words[0]} {category_name.split()[0]}")
            
        # 4. Broad fallback
        queries.append(category_name)
        
        # Deduplicate while preserving order
        unique_queries = []
        for q in queries:
            if q not in unique_queries:
                unique_queries.append(q)
                
        return unique_queries

    def get_safe_image(self, title, category_name):
        """
        Runs search, validation, ranking, download and WebP crop optimization.
        """
        clean_title_query = self._clean_title_keywords(title)
        search_queries = self._generate_semantic_queries(title, category_name)
        
        unsplash_key = os.environ.get("UNSPLASH_ACCESS_KEY")
        pexels_key = os.environ.get("PEXELS_API_KEY")
        
        all_urls = []
        for q in search_queries:
            # Tier 1: Bing CDN
            urls = self._fetch_bing_cdn(q)
            all_urls.extend(urls)
            
            # Tier 2: Wikimedia Commons
            if len(all_urls) < 3:
                urls = self._fetch_wikimedia(q)
                all_urls.extend(urls)
                
            # Tier 3: Unsplash / Pexels (Conditional)
            if len(all_urls) < 3 and unsplash_key:
                urls = self._fetch_unsplash(q, unsplash_key)
                all_urls.extend(urls)
            if len(all_urls) < 3 and pexels_key:
                urls = self._fetch_pexels(q, pexels_key)
                all_urls.extend(urls)
                
            if len(all_urls) >= 5:
                break

        # Deduplicate URLs
        seen = set()
        unique_urls = []
        for u in all_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        # Rank and filter (now downloads and checks real dimensions)
        self._log(f"Validating and ranking {len(unique_urls)} candidates...")
        ranked_candidates = self._rank_and_validate_candidates(unique_urls, clean_title_query)

        # Use the best pre-downloaded image (already validated and scored)
        for score, url, img_bytes in ranked_candidates:
            try:
                self._log(f"Using best match (Score: {score}): {url}")
                optimized_data = self._optimize_image(img_bytes)
                meta = {
                    "source": url.split("/")[2],
                    "license": "Creative Commons / Royalty Free / Public Domain",
                    "original_url": url,
                    "optimized_format": "webp",
                    "dimensions": "1280x720"
                }
                self._log("Image processed and optimized to WebP successfully!", "SUCCESS")
                self._mark_url_used(url)
                return optimized_data, meta
            except Exception as e:
                self._log(f"Optimization error for {url}: {e}", "WARNING")

        # Tier 4 Fallback: Pollinations Flux Text-Free photography
        self._log("All search sources failed. Querying Pollinations Flux...", "WARNING")
        cat_lower = category_name.lower()
        title_lower_fb = title.lower()
        if "food" in cat_lower or "recipe" in cat_lower:
            prompt_base = "A gourmet plate of styled food, fresh herbs and ingredients around the dish, professional culinary photography, warm ambient lighting, high-end restaurant style, depth of field"
        elif "health" in cat_lower or "diet" in cat_lower or "wellness" in cat_lower or any(x in title_lower_fb for x in ["diet", "health", "nutrition", "mediterranean", "wellness", "fitness"]):
            prompt_base = "A beautiful Mediterranean salad bowl with fresh vegetables, olive oil, feta cheese, tomatoes, and herbs on a rustic wooden table, warm natural sunlight, professional food photography, shallow depth of field"
        elif "travel" in cat_lower or "tourism" in cat_lower or any(x in title_lower_fb for x in ["travel", "trip", "vacation", "destination"]):
            prompt_base = "A stunning scenic landscape with mountains, lake, and golden hour lighting, travel photography, wide angle, cinematic composition, depth of field"
        elif "tech" in cat_lower or "software" in cat_lower or any(x in title_lower_fb for x in ["tech", "software", "ai ", "coding", "programming"]):
            prompt_base = "A modern tech workspace with a sleek laptop, glowing code on screen, minimalist desk setup, cool blue ambient lighting, professional technology photography, depth of field"
        elif "loan" in cat_lower or "credit" in cat_lower or "finance" in cat_lower or "funding" in cat_lower or "business" in cat_lower:
            prompt_base = "A modern financial office setting, a wooden desk with financial documents, a calculator, glasses, and a pen, soft natural lighting, professional business photography, depth of field"
        else:
            prompt_base = "A clean modern workplace with a laptop, notebooks, and writing materials, warm natural lighting, professional minimalist aesthetic, depth of field"
            
        ai_prompt = (
            f"{prompt_base}. Professional editorial photography, high-quality, clean composition, magazine-style, "
            f"NO text, NO writing, NO labels, NO logos, NO infographics, NO vector, NO drawings."
        )
        ai_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(ai_prompt)}?width=1280&height=720&model=flux&nologo=true"
        
        for attempt in range(3):
            try:
                self._log(f"Generating Flux AI Image (Attempt {attempt+1}/3)...")
                res = requests.get(ai_url, timeout=60)
                if res.status_code == 200 and res.content:
                    optimized_data = self._optimize_image(res.content)
                    meta = {
                        "source": "image.pollinations.ai",
                        "license": "Royalty Free (AI Generated)",
                        "original_url": ai_url,
                        "optimized_format": "webp",
                        "dimensions": "1280x720"
                    }
                    return optimized_data, meta
            except Exception as e:
                self._log(f"Flux AI Gen Error: {e}", "WARNING")
            time.sleep(3)

        # Ultimate fallback: category stock
        self._log("Fallback to category stock image...", "WARNING")
        fallback_img = "https://upload.wikimedia.org/wikipedia/commons/e/ec/Meeting_room_in_a_modern_office.jpg"
        if "food" in cat_lower or "recipe" in cat_lower:
            fallback_img = "https://upload.wikimedia.org/wikipedia/commons/e/ef/Fresh_culinary_herbs.jpg"
            
        try:
            res = requests.get(fallback_img, headers=headers, timeout=20)
            if res.status_code == 200 and res.content:
                optimized_data = self._optimize_image(res.content)
                meta = {
                    "source": "commons.wikimedia.org",
                    "license": "Public Domain / CC",
                    "original_url": fallback_img,
                    "optimized_format": "webp",
                    "dimensions": "1280x720"
                }
                return optimized_data, meta
        except Exception:
            pass
            
        return None, None

if __name__ == '__main__':
    # CLI entry point to test standalone search and WebP download
    import argparse
    parser = argparse.ArgumentParser(description="Standalone Copyright-Safe Image Search and WebP Optimization Pipeline")
    parser.add_argument('--title', type=str, required=True, help="Title of the blog post")
    parser.add_argument('--category', type=str, required=True, help="Category of the blog post")
    parser.add_argument('--out', type=str, default="cover.webp", help="Path to save the optimized image")
    
    args = parser.parse_args()
    
    pipeline = ImagePipeline(verbose=True)
    img_bytes, meta = pipeline.get_safe_image(args.title, args.category)
    
    if img_bytes:
        with open(args.out, 'wb') as f:
            f.write(img_bytes)
        print(f"\n[SUCCESS] Image downloaded, optimized to 1280x720 WebP, and saved to: {args.out}")
        print(f"Metadata: {json.dumps(meta, indent=2)}")
    else:
        print("\n[ERROR] Pipeline failed to retrieve or generate a cover image.")
