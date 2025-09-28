import os
import json
import re
import argparse
from datetime import datetime
import feedparser  # pip install feedparser

# === Load configs ===
with open("config/config.json", "r", encoding="utf-8") as f:
    base_config = json.load(f)

writer_config_path = "config/writer.json"
if os.path.exists(writer_config_path):
    with open(writer_config_path, "r", encoding="utf-8") as f:
        writer_config = json.load(f)
else:
    writer_config = {}

# === Parameters ===
MODEL = writer_config.get("model", "gpt-5-mini")
FALLBACK_MODEL = writer_config.get("fallbackModel", "gpt-5")
TEMP = writer_config.get("temperature", 0.4)
MIN_WORDS = writer_config.get("minWords", 1200)
MAX_WORDS = writer_config.get("maxWords", 1400)
SECTIONS = writer_config.get("sections", [
    "Introduction", "Background", "Analysis", "Impact", "Takeaways", "Sources"
])

PROMPT_SYSTEM = writer_config.get("prompt", {}).get("system", "")
PROMPT_USER_TEMPLATE = writer_config.get("prompt", {}).get("user", "")

# === Build prompt ===
def build_prompt(keyword, summaries):
    sections_enum = "\n".join([f"{i+1}. {sec}" for i, sec in enumerate(SECTIONS)])
    user_prompt = PROMPT_USER_TEMPLATE.format(
        keyword=keyword,
        summaries=summaries,
        MIN_WORDS=MIN_WORDS,
        MAX_WORDS=MAX_WORDS,
        SECTIONS_ENUM=sections_enum
    )
    return PROMPT_SYSTEM, user_prompt

# === Fake OpenAI call placeholder ===
# Replace with real API call in your environment
def call_openai(user_prompt, system_prompt):
    return f"""
# Introduction
This is a demo intro with keyword.

# Background
Context...

# Analysis
Analysis...

# Impact
Impact...

# Takeaways
- Point A
- Point B

# FAQ
Q: What is the main benefit?
A: The product saves time and hassle.

Q: Can it be used daily?
A: Yes, it is designed for daily use.

Q: Does it work internationally?
A: Absolutely, works worldwide.

Q: How accurate is it?
A: Very accurate within 0.1 unit.

# Sources
https://example.com
    """

# === Extract FAQ from article text ===
def extract_faq(article_text):
    faq_html = []
    faq_entities = []
    faq_section = re.search(r"# FAQ(.*?)(# Sources|$)", article_text, re.S)
    if faq_section:
        faq_block = faq_section.group(1).strip()
        qa_pairs = re.findall(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", faq_block, re.S)
        for q, a in qa_pairs:
            q_clean, a_clean = q.strip(), a.strip()
            # Visible HTML
            faq_html.append(
                f"<details><summary>{q_clean}</summary><p>{a_clean}</p></details>"
            )
            # JSON-LD entity
            faq_entities.append({
                "@type": "Question",
                "name": q_clean,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a_clean
                }
            })

    faq_block_html = ""
    faq_block_jsonld = ""

    if faq_html:
        faq_block_html = (
            "<section class=\"article-card\"><h3>FAQs</h3>\n"
            + "\n".join(faq_html)
            + "\n</section>"
        )

    if faq_entities:
        faq_json = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_entities
        }
        faq_block_jsonld = (
            '<script type="application/ld+json">\n'
            + json.dumps(faq_json, ensure_ascii=False, indent=2)
            + "\n</script>"
        )

    return faq_block_html, faq_block_jsonld

# === Save post ===
def save_post(keyword, html):
    today = datetime.today()
    folder = f"blog-src/posts/{today.year}/{today.month:02d}/{today.day:02d}"
    os.makedirs(folder, exist_ok=True)

    # slug из keyword
    slug = re.sub(r'[^a-z0-9\-]+', '-', keyword.lower()).strip('-')
    if not slug:
        slug = "post"

    filepath = os.path.join(folder, f"{slug}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Saved post to {filepath}")

# === Fetch news for auto mode ===
def fetch_news_from_rss():
    feeds = base_config.get("rssFeeds", [])
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                entry = feed.entries[0]
                keyword = entry.title
                summaries = f"{entry.title} — {entry.link}"
                return keyword, summaries
        except Exception as e:
            print(f"⚠️ Failed to parse {url}: {e}")
    return "demo keyword", "Headline — Source"

# === Main generate ===
def generate_post(keyword, summaries):
    sys_prompt, usr_prompt = build_prompt(keyword, summaries)
    text = call_openai(usr_prompt, sys_prompt)

    faq_html, faq_jsonld = extract_faq(text)

    # Construct HTML page with FAQ JSON-LD in <head>
    post_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{keyword} — Blog Post</title>
  <meta name="description" content="{keyword} article">
  {faq_jsonld}
</head>
<body>
  <article>
{text}
{faq_html}
  </article>
</body>
</html>
"""
    return post_html

# === Entry point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Auto mode for GitHub Actions")
    parser.add_argument("--keyword", type=str, default=None)
    parser.add_argument("--summaries", type=str, default=None)
    args = parser.parse_args()

    if args.auto:
        keyword, summaries = fetch_news_from_rss()
    else:
        keyword = args.keyword or "demo keyword"
        summaries = args.summaries or "Headline — Source"

    result = generate_post(keyword, summaries)
    save_post(keyword, result)
