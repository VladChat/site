import os, json, re, random, feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from .render import slugify

def _url_to_repo_path(u: str, base_prefix: str = "/site") -> str:
    """
    Convert a site URL to a repo-relative file path.
    Handles cases like "/posts/..." or "/site/posts/...".
    """
    u = (u or "").strip()
    if not u:
        return ""
    # force leading slash for local urls
    if not u.startswith(("http://", "https://", "/")):
        u = "/" + u
    # strip base prefix if present
    if base_prefix and u.startswith(base_prefix + "/"):
        u = u[len(base_prefix):]
    # finally strip the leading slash
    return u.lstrip("/")

def save_post(title, html, configs):
    """
    Save a post to posts/YYYY/MM/DD/<slug>-HHMMSS.html
    and update data/state.json (prepend newest).
    """
    today = datetime.today()
    folder = os.path.join("posts", f"{today.year:04d}", f"{today.month:02d}", f"{today.day:02d}")
    os.makedirs(folder, exist_ok=True)

    # Ensure unique slug to avoid overwriting previous posts with same title
    base_slug = slugify(title) or "post"
    unique_slug = f"{base_slug}-{today.strftime('%H%M%S')}"

    filepath = os.path.join(folder, f"{unique_slug}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    url = f"/posts/{today.year:04d}/{today.month:02d}/{today.day:02d}/{unique_slug}.html"

    # Short description for index
    try:
        desc = BeautifulSoup(html, "html.parser").find("article").get_text(" ", strip=True)
        desc = re.sub(r"\s+", " ", desc)[:200]
    except Exception:
        desc = f"{title} article"

    # Update state.json
    state_path = configs["state_path"]
    state = configs["state"] or {}
    state.setdefault("posts", [])

    # Prepend newest
    state["posts"].insert(0, {
        "title": title,
        "url": url,
        "date": today.strftime("%Y-%m-%d"),
        "description": desc,
        "tags": ["auto"]
    })

    # Keep only records that have a file in repo (defensive cleanup)
    # Accept both "/posts/..." and "/site/posts/..."
    cleaned = []
    seen_keys = set()
    for p in state["posts"]:
        path1 = _url_to_repo_path(p.get("url", ""), "/site")
        path2 = _url_to_repo_path(p.get("url", ""), "")  # also try without base
        exists = (os.path.exists(path1) or os.path.exists(path2))
        key = (p.get("title",""), p.get("date",""), p.get("url",""))
        if exists and key not in seen_keys:
            cleaned.append(p)
            seen_keys.add(key)
    state["posts"] = cleaned

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
