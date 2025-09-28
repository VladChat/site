import json
import math
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime

ROOT = Path(__file__).resolve().parent

def read_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def write_text(path: Path, txt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

# --- Load site config ---
SITE_ALL = read_json("config/config.json")
SITE = SITE_ALL.get("site", {})
BASE = (SITE.get("base_url") or "").rstrip("/")
SITE_URL = (SITE.get("url") or "").rstrip("/")
POSTS_PER_PAGE = int(SITE.get("posts_per_page", 20))  # регулируется в config.json

STATE_PATH = ROOT / "data/state.json"
STATE = read_json("data/state.json")

# --- Normalize state (URLs, dedup) ---
def normalize_state():
    changed = False
    posts = STATE.get("posts", []) or []
    norm_posts = []
    seen = set()

    for p in posts:
        p = dict(p)
        url = (p.get("url") or "").strip()
        url_orig = url

        # Приводим к относительному виду и с одинарным /site
        if url and not url.startswith(("/", "http://", "https://")):
            url = "/" + url
        if url.startswith("/site/site/"):
            url = url[len("/site"):]
        if BASE and url.startswith(BASE + "/"):
            url = url[len(BASE):]
        if url.startswith("/site/posts/"):
            url = url[len("/site"):]

        if url != url_orig:
            changed = True

        p["url"] = url

        key = (p.get("title", ""), p.get("date", ""), p["url"])
        if key not in seen:
            norm_posts.append(p)
            seen.add(key)
        else:
            changed = True

    if changed:
        STATE["posts"] = norm_posts
        STATE_PATH.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
        print("🧹 Normalized data/state.json")

# --- Build paginated index pages ---
def build_main_and_pages():
    posts = STATE.get("posts", []) or []
    total = len(posts)
    pages = max(1, math.ceil(total / POSTS_PER_PAGE))

    template_path = ROOT / "templates" / "index.html"
    tpl = template_path.read_text(encoding="utf-8")
    soup_template = BeautifulSoup(tpl, "html.parser")

    for page in range(1, pages + 1):
        start = (page - 1) * POSTS_PER_PAGE
        end = start + POSTS_PER_PAGE
        page_posts = posts[start:end]

        soup = BeautifulSoup(str(soup_template), "html.parser")
        lst = soup.find(id="list")
        if lst:
            lst.clear()
            for p in page_posts:
                a = soup.new_tag("a", href=f"{SITE_URL}{BASE}{p['url']}")
                a.string = p.get("title") or "Untitled"
                card = soup.new_tag("div", **{"class": "article-card"})
                meta = soup.new_tag("div", **{"class": "meta"})
                meta.string = p.get("date", "")
                desc = soup.new_tag("p")
                desc.string = p.get("description", "")
                card.append(a); card.append(meta); card.append(desc)
                lst.append(card)

        # Сохраняем страницу
        if page == 1:
            out_path = ROOT / "index.html"
        else:
            out_path = ROOT / "page" / str(page) / "index.html"
        write_text(out_path, str(soup))

    # Быстрый клиентский индекс для поиска (ограничим 200)
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    write_text(feeds_dir / "search.json", json.dumps(posts[:200], ensure_ascii=False, indent=2))
    print(f"✅ Rebuilt {pages} index pages with pagination")

# --- Build RSS and sitemap ---
def build_sitemap_and_rss():
    posts = STATE.get("posts", []) or []
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)

    # Sitemap
    urls = []
    for p in posts:
        urls.append(f"{SITE_URL}{BASE}{p['url']}")
    xml = ["<?xml version='1.0' encoding='UTF-8'?>", "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for u in urls:
        xml.append(f"<url><loc>{u}</loc></url>")
    xml.append("</urlset>")
    write_text(feeds_dir / "sitemap.xml", "\n".join(xml))

    # RSS
    rss = ["<?xml version='1.0' encoding='UTF-8'?>", "<rss version='2.0'><channel>"]
    rss.append(f"<title>{SITE.get('name','Blog')}</title>")
    rss.append(f"<link>{SITE_URL}{BASE}</link>")
    rss.append("<description>Automated blog feed</description>")
    for p in posts[:100]:
        link = f"{SITE_URL}{BASE}{p['url']}"
        title = (p.get("title") or "").replace("&", "&amp;")
        desc = (p.get("description") or "").replace("&", "&amp;")
        pub = p.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
        rss.append(f"<item><title><![CDATA[{title}]]></title><link>{link}</link><pubDate>{pub}</pubDate><description><![CDATA[{desc}]]></description></item>")
    rss.append("</channel></rss>")
    write_text(feeds_dir / "rss.xml", "\n".join(rss))
    print("🗺️ sitemap.xml & 📰 rss.xml rebuilt")

# --- Fix root shells meta site-base ---
def fix_root_shells():
    for rel in ["index.html", "search.html", "privacy.html", "terms.html", "404.html"]:
        path = ROOT / rel
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        head = soup.find("head") or soup
        meta = head.find("meta", attrs={"name": "site-base"})
        if not meta:
            meta = soup.new_tag("meta", attrs={"name": "site-base", "content": f"{SITE_URL}{BASE}"})
            head.append(meta)
        else:
            meta["content"] = f"{SITE_URL}{BASE}"
        path.write_text(str(soup), encoding="utf-8")
    print("✅ Fixed root shells (meta site-base)")

if __name__ == "__main__":
    normalize_state()
    build_main_and_pages()
    build_sitemap_and_rss()
    fix_root_shells()
    print("🏁 Rebuild finished")
