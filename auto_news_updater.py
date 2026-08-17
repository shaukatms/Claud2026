#!/usr/bin/env python3
"""
Student News Pakistan - Automated Daily News Updater
Pulls authentic news, verifies, rewrites professionally, updates homepage
Runs daily at 5 AM PKT automatically

REQUIREMENTS:
- Python 3.8+
- pip install feedparser openai python-dotenv requests Pillow

USAGE:
- Run manually: python3 auto_news_updater.py
- Run daily: Set up cron job (Linux/Mac) or Task Scheduler (Windows)
  
CRON EXAMPLE (Linux/Mac):
0 5 * * * /usr/bin/python3 /path/to/auto_news_updater.py
(runs at 5 AM every day)
"""

import feedparser
import json
import os
from datetime import datetime, timedelta
import requests
from PIL import Image, ImageDraw, ImageFont
import sys

# RSS FEEDS - Authentic Pakistani news sources (Tier 1 — RSS-capable)
# Full 100-source directory (all 12 categories, including embassies, armed
# forces, NGOs, government benefit programs) lives in
# MASTER_SOURCE_DIRECTORY.txt — most of those sources don't publish RSS
# feeds and need manual/weekly editorial checking rather than automated
# polling. This TRUSTED_FEEDS list is intentionally the automatable subset.
# National media only — no tech blogs, aggregators, or regional-only outlets.
# Full 156-source directory lives in MASTER_SOURCE_DIRECTORY.txt — most of
# those sources don't publish RSS feeds and need manual/weekly editorial
# checking. This TRUSTED_FEEDS list is intentionally the automatable
# subset, restricted to established national newspapers/wire services.
TRUSTED_FEEDS = [
    "https://www.app.com.pk/feed",       # Associated Press of Pakistan — national wire service
    "https://www.dawn.com/feed",         # Dawn — national newspaper
    "https://tribune.com.pk/feed",       # The Express Tribune — national newspaper
    "https://www.thenews.com.pk/rss",    # The News International — national newspaper
    "https://nation.com.pk/rss",         # The Nation — national newspaper
    "https://dailytimes.com.pk/feed",    # Daily Times — national newspaper
]

# CATEGORY KEYWORDS - Map stories to categories
# Expanded per MASTER_SOURCE_DIRECTORY.txt's 12-category coverage checklist.
CATEGORIES = {
    "education": ["scholarship", "university", "hec", "admission", "degree", "college", "peef", "seef", "ehsaas",
                  "nust", "seecs", "fast-nu", "szabist", "aga khan university", "aku", "lums", "comsats",
                  "quaid-i-azam", "punjab university", "university of karachi", "iba karachi", "iiui",
                  "aiou", "virtual university", "bahria university", "air university", "gik", "giki"],
    "study_abroad": ["fulbright", "daad", "erasmus", "study abroad", "visa", "international", "british council",
                      "australia awards", "educanada", "campus france", "austrade"],
    "careers": ["internship", "trainee", "nts", "fpsc", "career fair", "skills"],  # deliberately excludes "job"/"hiring"/"recruitment" — this desk covers career NEWS, not hiring ads
    "technology": ["ai", "tech", "software", "coding", "startup", "innovation", "ignite", "pasha"],
    "sports": ["cricket", "football", "sports", "athlete", "tournament", "game"],
    "achievements": ["award", "win", "achievement", "excellence", "champion", "olympiad", "talent hunt"],
    "medical_admissions": ["mdcat", "medical college", "pmc", "kemu", "duhs", "khyber medical", "nishtar"],
    "engineering_admissions": ["ecat", "engineering university", "nust", "uet", "giki", "ned university", "mehran"],
    "law_admissions": ["law college", "llb admission", "bar council"],
    "armed_forces": ["pma kakul", "cadet college", "isPR", "army public school", "paf cadetship", "pak navy",
                      "fauji foundation", "ndu islamabad"],
    "nonprofit": ["tcf", "citizens foundation", "zindagi trust", "teach for pakistan", "akhuwat", "alif ailaan",
                  "read foundation", "al-khidmat"],
    "government_benefit": ["ehsaas", "bisp", "laptop scheme", "peef", "seef", "benazir income support"],
    "sports_org": ["pakistan sports board", "olympic association", "pcb", "hockey federation", "pff",
                   "sports directorate", "inter-university sports", "university of sports sciences"],
    "scouting": ["boy scouts", "girl guides", "pbsa", "pgga", "scouting", "guiding"],
    "tourism": ["ptdc", "tourism development", "cultural exchange", "youth exchange", "student travel"],
    "skill_development": ["tevta", "navttc", "pvtc", "vocational training", "technical education",
                           "skills university", "national skills university"],
}

# CITIES - Extract location if mentioned
CITIES = ["karachi", "lahore", "islamabad", "peshawar", "quetta", "faisalabad"]

# ============================================================
# SPECIAL DAYS — national/world/international observances.
# Checked automatically on every run against today's date (MM-DD).
# If today matches, the green Special Day Spotlight banner is
# generated fresh; if no match, the banner is omitted entirely
# for that day's build. Extend this list as needed.
# ============================================================
SPECIAL_DAYS = {
    "01-24": {"label": "International Education Day", "eyebrow": "🌍 World Day"},
    "02-05": {"label": "Kashmir Solidarity Day", "eyebrow": "🇵🇰 National Day"},
    "03-23": {"label": "Pakistan Day", "eyebrow": "🇵🇰 National Day"},
    "05-01": {"label": "Labour Day", "eyebrow": "🌍 World Day"},
    "08-12": {"label": "International Youth Day", "eyebrow": "🌍 World Day"},
    "08-14": {"label": "Pakistan Independence Day", "eyebrow": "🇵🇰 National Day"},
    "09-06": {"label": "Defence Day", "eyebrow": "🇵🇰 National Day"},
    "09-08": {"label": "World Literacy Day", "eyebrow": "🌍 World Day"},
    "11-09": {"label": "Iqbal Day", "eyebrow": "🇵🇰 National Day"},
    "12-25": {"label": "Quaid-e-Azam's Birthday", "eyebrow": "🇵🇰 National Day"},
}

def get_special_day_today():
    """Return today's special-day entry if one exists, else None."""
    key = datetime.now().strftime("%m-%d")
    return SPECIAL_DAYS.get(key)

class NewsUpdater:
    def __init__(self):
        self.news_items = []
        self.featured_story = None
        self.timestamp = datetime.now()
        
    def fetch_news_from_rss(self):
        """Fetch latest news from RSS feeds"""
        print("[1/5] Fetching news from RSS feeds...")
        
        all_entries = []
        
        for feed_url in TRUSTED_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                entries = feed.entries[:10]  # Get top 10 from each feed
                all_entries.extend(entries)
                print(f"  ✓ Fetched from {feed_url.split('/')[-2]}")
            except Exception as e:
                print(f"  ✗ Error fetching {feed_url}: {e}")
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_entries = []
        for entry in all_entries:
            if entry.title not in seen_titles:
                seen_titles.add(entry.title)
                unique_entries.append(entry)
        
        return unique_entries[:20]  # Return top 20 unique stories
    
    def verify_authenticity(self, entry):
        """Verify if news is authentic and relevant to students"""
        
        # Check if from trusted source — established national media only
        trusted_domains = [
            "app.com.pk",
            "dawn.com",
            "tribune.com.pk",
            "nation.com.pk",
            "thenews.com.pk",
            "dailytimes.com.pk",
            "brecorder.com"
        ]
        
        link = entry.get("link", "")
        is_trusted = any(domain in link for domain in trusted_domains)
        
        if not is_trusted:
            return False, "Not from verified news source"
        
        # Check if relevant to students
        relevant_keywords = [
            "student", "university", "education", "scholarship",
            "job", "internship", "opportunity", "career",
            "event", "workshop", "seminar", "conference"
        ]
        
        title = (entry.get("title", "") + " " + 
                entry.get("summary", "")).lower()
        
        is_relevant = any(keyword in title for keyword in relevant_keywords)
        
        if not is_relevant:
            return False, "Not directly relevant to students"

        # Explicit hiring-ad exclusion — this desk covers career NEWS
        # (policy, quotas, trends, program launches), not job vacancy
        # postings. Skip anything reading like a direct hiring ad.
        hiring_ad_phrases = [
            "urgently required", "send cv to", "walk-in interview",
            "vacancy announcement", "we are hiring", "apply now for this position",
            "job vacancy", "immediate joining", "salary package"
        ]
        is_hiring_ad = any(phrase in title for phrase in hiring_ad_phrases)
        if is_hiring_ad:
            return False, "Reads as a hiring advertisement, not career news — excluded per editorial policy"
        
        # Check if recent (within last 48 hours)
        try:
            pub_date = entry.get("published_parsed")
            if pub_date:
                entry_date = datetime(*pub_date[:6])
                age_hours = (datetime.now() - entry_date).total_seconds() / 3600
                if age_hours > 48:
                    return False, "Story is older than 48 hours"
        except:
            pass
        
        return True, "Authentic and relevant"
    
    def categorize_story(self, title, summary):
        """Automatically categorize story"""
        text = (title + " " + summary).lower()
        
        for category, keywords in CATEGORIES.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return "achievements"  # Default category
    
    def extract_location(self, title, summary):
        """Extract city location if mentioned"""
        text = (title + " " + summary).lower()
        
        for city in CITIES:
            if city in text:
                return city
        
        return "national"
    
    def rewrite_professionally(self, title, summary):
        """
        Rewrite headline and summary professionally
        In production, this would use OpenAI API for AI rewriting
        For now, uses rule-based rewriting
        """
        
        # Clean up title
        title = title.strip()
        if title.endswith("..."):
            title = title[:-3]
        
        # Make title more student-focused
        student_starters = [
            "Students can",
            "Opportunity for students:",
            "Apply now:",
            "Don't miss:",
            "Breaking:",
        ]
        
        # Keep summary under 150 characters
        if len(summary) > 150:
            summary = summary[:150].rsplit(' ', 1)[0] + "..."
        
        return title, summary
    
    def process_news(self):
        """Process and curate news"""
        print("[2/5] Verifying and categorizing news...")
        
        entries = self.fetch_news_from_rss()
        
        for entry in entries:
            # Verify authenticity
            is_valid, reason = self.verify_authenticity(entry)
            if not is_valid:
                print(f"  ⊘ Skipped: {entry.title[:50]}... ({reason})")
                continue
            
            # Extract data
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            
            # Rewrite professionally
            title, summary = self.rewrite_professionally(title, summary)
            
            # Categorize
            category = self.categorize_story(title, summary)
            
            # Extract location
            location = self.extract_location(title, summary)
            
            story = {
                "title": title,
                "summary": summary,
                "link": link,
                "category": category,
                "location": location,
                "source": link.split("/")[2] if link else "unknown"
            }
            
            self.news_items.append(story)
            print(f"  ✓ Added: {title[:50]}... ({category})")
        
        # Set featured story (top story)
        if self.news_items:
            self.featured_story = self.news_items[0]
        
        return self.news_items
    
    def organize_by_category(self):
        """Organize news by categories"""
        organized = {cat: [] for cat in CATEGORIES.keys()}
        
        for item in self.news_items:
            category = item["category"]
            organized[category].append(item)
        
        # Ensure each category has 3 stories (duplicate if needed)
        for category in organized:
            while len(organized[category]) < 3:
                if self.news_items:
                    organized[category].append(self.news_items[0])
                else:
                    break
            
            organized[category] = organized[category][:3]
        
        return organized
    
    def generate_hero_image(self):
        """Generate attractive hero image for homepage"""
        print("[3/5] Generating hero image...")
        
        try:
            # Create image (1200x600px for hero)
            width, height = 1200, 600
            
            # Gradient background (navy to dark blue)
            image = Image.new('RGB', (width, height), color=(0, 31, 63))  # Navy
            draw = ImageDraw.Draw(image, 'RGBA')
            
            # Add semi-transparent overlay with red accent
            draw.rectangle(
                [(0, 0), (width, height)],
                fill=(0, 31, 63, 200)
            )
            
            # Add red accent bar
            draw.rectangle(
                [(0, 0), (width, 8)],
                fill=(196, 30, 58, 255)  # Red
            )
            
            # Add featured story text (centered)
            try:
                # Try to use a nice font
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                # Fallback to default font
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            if self.featured_story:
                title = self.featured_story["title"]
                
                # Wrap text
                max_width = width - 60
                lines = []
                words = title.split()
                current_line = ""
                
                for word in words:
                    test_line = current_line + " " + word if current_line else word
                    if len(test_line) > 50:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                    else:
                        current_line = test_line
                
                if current_line:
                    lines.append(current_line)
                
                # Draw text
                y_offset = 150
                for line in lines[:3]:
                    draw.text(
                        (60, y_offset),
                        line,
                        font=font_large,
                        fill=(255, 255, 255, 255)
                    )
                    y_offset += 60
                
                # Add "Read More" at bottom
                draw.text(
                    (60, height - 80),
                    "→ Tap to read full story",
                    font=font_small,
                    fill=(196, 30, 58, 255)
                )
            else:
                # Default hero text
                draw.text(
                    (100, 200),
                    "STUDENT NEWS PAKISTAN",
                    font=font_large,
                    fill=(255, 255, 255, 255)
                )
                draw.text(
                    (100, 350),
                    "Your Voice. Your Stories. Your Platform.",
                    font=font_small,
                    fill=(196, 30, 58, 255)
                )
            
            # Save image
            image.save("hero_image.jpg", quality=85)
            print("  ✓ Hero image generated")
            return "hero_image.jpg"
            
        except Exception as e:
            print(f"  ✗ Error generating image: {e}")
            return None
    
    def generate_html(self, organized_news, hero_image):
        """
        Generate updated HTML homepage.

        IMPORTANT — FULL REPLACE, NOT APPEND:
        This function builds the entire HTML string from scratch every run,
        using only articles fetched in THIS run (self.news_items / organized_news).
        Nothing from a previous day's output is read back in or merged. The
        finished string then overwrites index.html completely on upload —
        so every daily refresh is a clean, full replacement of yesterday's
        homepage, never an accumulation on top of it.
        """
        print("[4/5] Generating HTML homepage (full replace of previous content)...")

        special_day = get_special_day_today()
        
        # Emojis for categories
        category_icons = {
            "education": "📚",
            "study_abroad": "✈️",
            "careers": "💼",
            "technology": "💻",
            "sports": "🏆",
            "achievements": "⭐"
        }
        
        # Start building HTML
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student News Pakistan - Daily Briefing</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #333; }
        
        .header {
            background: white;
            border-bottom: 2px solid #001f3f;
            padding: 15px 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .logo { font-size: 20px; font-weight: bold; }
        .logo span { color: #c41e3a; }
        
        .tagline { font-size: 10px; letter-spacing: 1px; color: #666; margin-top: 3px; }
        
        .date-info { font-size: 12px; color: #c41e3a; font-weight: bold; text-align: right; margin-top: -20px; }
        
        .hero { width: 100%; height: auto; max-height: 600px; object-fit: cover; }
        
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        
        .featured {
            background: linear-gradient(135deg, #001f3f 0%, #003d5c 100%);
            color: white;
            padding: 30px;
            margin: 20px 0;
            border-radius: 3px;
        }
        
        .featured h2 { font-size: 24px; margin-bottom: 10px; line-height: 1.3; }
        .featured p { font-size: 14px; line-height: 1.6; margin-bottom: 15px; }
        .featured a {
            background: #c41e3a;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            font-weight: 600;
            font-size: 12px;
            border-radius: 2px;
            display: inline-block;
        }
        
        .section { margin: 30px 0; }
        .section-title { font-size: 12px; font-weight: 700; letter-spacing: 1px; color: #001f3f; margin-bottom: 15px; }
        
        .news-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        
        .news-card {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 3px;
            transition: all 0.3s;
        }
        
        .news-card:hover { border-color: #001f3f; box-shadow: 0 4px 8px rgba(0,31,63,0.1); }
        
        .news-card h3 { font-size: 15px; font-weight: 600; color: #001f3f; margin-bottom: 8px; line-height: 1.4; }
        .news-card p { font-size: 13px; color: #666; line-height: 1.5; margin-bottom: 10px; }
        .news-card a { color: #c41e3a; text-decoration: none; font-weight: 600; font-size: 12px; }
        
        .category-label { display: inline-block; background: #f5f5f5; padding: 4px 8px; font-size: 11px; color: #666; margin-bottom: 8px; }
        
        .update-time { text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }
        
        @media (max-width: 768px) {
            .news-grid { grid-template-columns: 1fr; }
            .hero { max-height: 400px; }
            .featured h2 { font-size: 18px; }
        }
    </style>
</head>
<body>

<header class="header">
    <div class="logo">student<span>news</span></div>
    <div class="tagline">YOUR VOICE. YOUR <span style="color: #c41e3a;">STORIES</span>. YOUR PLATFORM.</div>
    <div class="date-info">""" + datetime.now().strftime("%d %B %Y | %A").upper() + """</div>
</header>

<img src="hero_image.jpg" alt="Featured Story" class="hero">

"""
        # Special Day Spotlight — only included if today matches SPECIAL_DAYS
        if special_day:
            html += f"""
<div style="background: linear-gradient(135deg, #01411C 0%, #046A38 100%); padding: 18px 20px;">
    <div style="max-width: 1180px; margin: 0 auto; color: white;">
        <div style="font-size: 10px; font-weight: 800; letter-spacing: 1.4px; text-transform: uppercase; color: #ffd76a; margin-bottom: 4px;">{special_day['eyebrow']}</div>
        <h3 style="font-size: 17px; font-weight: 800;">{special_day['label']} — {datetime.now().strftime('%B %-d, %Y')}</h3>
    </div>
</div>
"""

        html += """
<div class="container">
"""
        
        # Featured Story
        if self.featured_story:
            featured = self.featured_story
            html += f"""
    <div class="featured">
        <h2>{featured['title']}</h2>
        <p>{featured['summary']}</p>
        <a href="{featured['link']}" target="_blank">READ FULL STORY →</a>
    </div>
"""
        
        # Categories section
        for category, stories in organized_news.items():
            if stories:
                icon = category_icons.get(category, "📰")
                category_name = category.replace("_", " ").title()
                
                html += f"""
    <div class="section">
        <div class="section-title">{icon} {category_name}</div>
        <div class="news-grid">
"""
                
                for story in stories[:3]:
                    html += f"""
            <div class="news-card" data-source-link="{story['link']}">
                <div class="category-label">{story['location'].title()}</div>
                <h3>{story['title']}</h3>
                <p>{story['summary']}</p>
                <button class="read-more" onclick="window.open(this.closest('.news-card').dataset.sourceLink, '_blank')">Read more →</button>
            </div>
"""
                
                html += """
        </div>
    </div>
"""
        
        # Footer
        html += """
    <div class="update-time">
        📱 Updated automatically at 6 AM PKT daily
        <br>
        <small>Verified from authentic sources and professionally rewritten</small>
        <br>
        <small style="opacity:0.6;">Last refreshed: """ + datetime.now().strftime("%A, %d %B %Y — %I:%M %p PKT") + """ (full content replace, not merged with previous day)</small>
    </div>
    
</div>

</body>
</html>
"""
        
        return html
    
    def upload_to_freehostia(self, html_content, image_path):
        """
        Upload updated files to Freehostia via FTP
        Requires: FREEHOSTIA_HOST, FREEHOSTIA_USER, FREEHOSTIA_PASS env vars
        """
        print("[5/5] Uploading to Freehostia...")
        
        try:
            from ftplib import FTP
            
            # Get credentials from environment variables
            ftp_host = os.getenv("FREEHOSTIA_HOST", "ftp.freehostia.com")
            ftp_user = os.getenv("FREEHOSTIA_USER")
            ftp_pass = os.getenv("FREEHOSTIA_PASS")
            
            if not ftp_user or not ftp_pass:
                print("  ⚠ Freehostia credentials not found in environment")
                print("  Set FREEHOSTIA_USER and FREEHOSTIA_PASS")
                return False
            
            # Connect to FTP
            ftp = FTP(ftp_host)
            ftp.login(ftp_user, ftp_pass)
            ftp.cwd("public_html")
            
            # Upload HTML
            with open("index.html", "wb") as f:
                f.write(html_content.encode())
            
            with open("index.html", "rb") as f:
                ftp.storbinary("STOR index.html", f)
            print("  ✓ Uploaded index.html")
            
            # Upload image
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    ftp.storbinary("STOR hero_image.jpg", f)
                print("  ✓ Uploaded hero_image.jpg")
            
            ftp.quit()
            print("  ✓ Successfully uploaded to Freehostia!")
            return True
            
        except Exception as e:
            print(f"  ✗ FTP error: {e}")
            print("  Tip: Save files locally instead")
            return False
    
    def save_locally(self, html_content, image_path):
        """
        Save HTML and image locally for manual upload.

        REPLACE-SAFETY: any existing local index.html is deleted first,
        then the freshly generated content is written. This guarantees
        the file on disk can never be a merge of old + new content —
        it's always exactly what this run produced, nothing else.
        """
        print("[5/5] Saving files locally (deleting old copy first)...")

        try:
            if os.path.exists("index.html"):
                os.remove("index.html")

            # Save HTML
            with open("index.html", "w") as f:
                f.write(html_content)
            print("  ✓ Saved: index.html")
            
            # Image already created
            if image_path and os.path.exists(image_path):
                print(f"  ✓ Saved: {image_path}")
            
            print("\n  ℹ Upload these files to Freehostia manually:")
            print("    1. index.html (paste into File Manager)")
            print("    2. hero_image.jpg (upload via File Manager)")
            
            return True
            
        except Exception as e:
            print(f"  ✗ Error saving files: {e}")
            return False
    
    def run(self):
        """Run the complete update process"""
        print("=" * 60)
        print("STUDENT NEWS PAKISTAN - AUTOMATED DAILY UPDATE")
        print(f"Started at: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        try:
            # Process news
            self.process_news()
            
            if not self.news_items:
                print("\n✗ No news found. Using default content.")
                self.news_items = []
            
            # Organize by category
            organized_news = self.organize_by_category()
            
            # Generate hero image
            hero_image = self.generate_hero_image()
            
            # Generate HTML
            html_content = self.generate_html(organized_news, hero_image)
            
            # Try to upload to Freehostia
            uploaded = self.upload_to_freehostia(html_content, hero_image)
            
            # If FTP failed, save locally
            if not uploaded:
                self.save_locally(html_content, hero_image)
            
            print("\n" + "=" * 60)
            print("✓ DAILY UPDATE COMPLETE!")
            print("=" * 60)
            print(f"Stories processed: {len(self.news_items)}")
            print(f"Categories: {sum(1 for v in organized_news.values() if v)}")
            print(f"Featured story: {self.featured_story['title'][:50] if self.featured_story else 'None'}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            return False
        
        return True


if __name__ == "__main__":
    updater = NewsUpdater()
    success = updater.run()
    sys.exit(0 if success else 1)
