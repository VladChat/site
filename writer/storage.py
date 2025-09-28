import os, json, re, feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from .render import slugify

def save_post(title, html, configs):
    today = datetime.today()
    folder = os.path.join("posts", f"{today.year:04d}", f"{today.month:02d}", f"{today.day:02d}")
    os.makedirs(folder, exist_ok=True)

    slug = slugify(title) or "post"
    filepath = os.path.join(folder, f"{slug}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    url = f"/posts/{today.year:04d}/{today.month:02d}/{today.day:02d}/{slug}.html"
    try:
        desc = BeautifulSoup(html, "html.parser").find("article").get_text(" ", strip=True)
        desc = re.sub(r"\s+", " ", desc)[:200]
    except Exception:
        desc = f"{title} article"

    state_path = configs["state_path"]
    state = configs["state"]
    state.setdefault("posts", [])
    state["posts"].insert(0, {
        "title": title,
        "url": url,
        "date": today.strftime("%Y-%m-%d"),
        "description": desc,
        "tags": ["auto"]
    })

    def url_to_path(u: str): return u.lstrip("/")
    state["posts"] = [p for p in state["posts"] if os.path.exists(url_to_path(p.get("url", "")))]

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved post to {filepath} and updated state.json")

def fetch_news_from_rss(configs):
    feeds = configs.get("feeds", [])
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                e = feed.entries[0]
                return e.title, f"{e.title} — {e.link}"
        except Exception as e:
            print(f"⚠️ Failed to parse {url}: {e}")
    return "demo keyword", "Headline — Source"
