import os, json, re, random, feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from .render import slugify


def build_post_slug(title, when=None):
    """Return a timestamped slug for a post and the datetime used.

    The datetime is returned so other components can reuse the same
    timestamp when building paths or canonical URLs.
    """
    when = when or datetime.today()
    base_slug = slugify(title) or "post"
    return f"{base_slug}-{when.strftime('%H%M%S')}", when


def save_post(title, html, configs, *, slug, published_at=None):
    """
    Save a post to posts/YYYY/MM/DD/<slug>.html
    and update data/state.json (prepend newest).
    """
    published_at = published_at or datetime.today()
    folder = os.path.join(
        "posts",
        f"{published_at.year:04d}",
        f"{published_at.month:02d}",
        f"{published_at.day:02d}",
    )
    os.makedirs(folder, exist_ok=True)
    if not slug:
        slug, _ = build_post_slug(title, when=published_at)

    filepath = os.path.join(folder, f"{slug}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    url = (
        f"/posts/{published_at.year:04d}/"
        f"{published_at.month:02d}/"
        f"{published_at.day:02d}/{slug}.html"
    )

    # Short description for index
    try:
        desc = BeautifulSoup(html, "html.parser").find("article").get_text(" ", strip=True)
        desc = re.sub(r"\s+", " ", desc)[:200]
    except Exception:
        desc = f"{title} article"

    # Update state.json
    state_path = configs["state_path"]
    state = configs.get("state") or {}
    state.setdefault("posts", [])

    # Prepend newest
    state["posts"].insert(0, {
        "title": title,
        "url": url,
        "date": published_at.strftime("%Y-%m-%d"),
        "description": desc,
        "tags": ["auto"]
    })

    # ❌ Больше нет агрессивной фильтрации старых постов.
    # Все старые записи остаются в state.json, даже если файл временно отсутствует.

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved post to {filepath} and updated state.json")


def fetch_news_from_rss(configs):
    """
    Fetch a headline + link from configured RSS feeds.
    Strategy:
      - Shuffle feeds for variability.
      - Collect first 3–5 entries from each feed (if available).
      - Pick the most recent by published date; fallback to the first available.
    Returns (title, summary_line).
    """
    feeds = list(configs.get("feeds", [])) or []
    if not feeds:
        return "demo keyword", "Headline — Source"

    random.shuffle(feeds)
    candidates = []

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in (feed.entries or [])[:5]:
                title = getattr(e, "title", "") or ""
                link = getattr(e, "link", "") or ""
                if not title or not link:
                    continue
                # Try to get a datetime; feedparser puts it in 'published_parsed' or 'updated_parsed'
                ts = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
                epoch = 0
                if ts:
                    try:
                        epoch = int(datetime(*ts[:6]).timestamp())
                    except Exception:
                        epoch = 0
                candidates.append((epoch, title, f"{title} — {link}"))
        except Exception as ex:
            print(f"⚠️ Failed to parse {url}: {ex}")

    if not candidates:
        return "demo keyword", "Headline — Source"

    # most recent first
    candidates.sort(key=lambda x: x[0], reverse=True)
    _, title, line = candidates[0]
    return title, line
