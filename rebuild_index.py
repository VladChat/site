import os, json
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parent

def read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def write_text(path: Path, txt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

# --- Load site + state ---
SITE_ALL = read_json("config/config.json")
SITE = SITE_ALL.get("site", {})
BASE = SITE.get("base_url", "").rstrip("/")            # напр. "/site" или ""
SITE_URL = SITE.get("url", "").rstrip("/")             # напр. "https://vladchat.github.io"

STATE_PATH = ROOT / "data/state.json"
STATE = read_json("data/state.json")

# --- Normalize state: ensure urls always start with /posts/... ---
def normalize_state():
    changed = False
    posts = STATE.get("posts", [])
    norm_posts = []
    seen = set()

    for p in posts:
        url_orig = p.get("url", "") or ""
        url = url_orig

        # ensure leading slash
        if url and not url.startswith(("http://", "https://", "/")):
            url = "/" + url

        # strip accidental double prefix
        if url.startswith("/site/site/"):
            url = url[len("/site"):]
        if BASE and url.startswith(BASE + "/"):
            url = url[len(BASE):]
        if url.startswith("/site/posts/"):
            url = url[len("/site"):]

        if url != url_orig:
            changed = True
        p["url"] = url

        key = (p.get("title",""), p.get("date",""), p["url"])
        if key not in seen:
            norm_posts.append(p)
            seen.add(key)
        else:
            # просто пропускаем дубликаты, но не трогаем остальные посты
            changed = True

    if changed:
        STATE["posts"] = norm_posts
        STATE_PATH.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
        print("🧹 Normalized data/state.json")

# --- Build main index.html ---
def build_main():
    posts = STATE.get("posts", [])[:50]
    home_path = ROOT / "index.html"
    soup = BeautifulSoup(home_path.read_text(encoding="utf-8"), "html.parser")

    list_div = soup.find(id="list")
    if list_div:
        list_div.clear()

    for p in posts:
        item = soup.new_tag("div", attrs={"class": "article-card"})

        href = f"{BASE}{p['url']}" if isinstance(p.get("url"), str) else "#"
        a = soup.new_tag("a", href=href)
        a.string = p.get("title", "Untitled")

        meta = soup.new_tag("div", attrs={"class": "meta"})
        meta.string = p.get("date", "")

        desc = soup.new_tag("p")
        desc.string = p.get("description", "")

        item.append(a)
        item.append(meta)
        item.append(desc)
        if list_div:
            list_div.append(item)

    home_path.write_text(str(soup), encoding="utf-8")
    # also write feeds/search.json
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    write_text(feeds_dir / "search.json", json.dumps(STATE.get("posts", [])[:200], ensure_ascii=False, indent=2))
    print("✅ Rebuilt main index.html + feeds/search.json")

# --- Build sitemap.xml & rss.xml ---
def build_sitemap_and_rss():
    posts = STATE.get("posts", [])[:500]

    # sitemap.xml
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in posts:
        loc = f"{SITE_URL}{BASE}{p['url']}" if SITE_URL else f"{BASE}{p['url']}"
        lastmod = p.get("date", "")
        sitemap.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    sitemap.append("</urlset>")
    write_text(ROOT / "sitemap.xml", "\n".join(sitemap))

    # rss.xml
    rss = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           f"<title>{SITE.get('name','Blog')}</title>",
           f"<link>{SITE_URL}{BASE}/</link>" if SITE_URL else f"<link>{BASE}/</link>",
           f"<description>{SITE.get('name','Automated Blog')}</description>"]
    for p in posts[:50]:
        loc = f"{SITE_URL}{BASE}{p['url']}" if SITE_URL else f"{BASE}{p['url']}"
        try:
            pubdate = format_datetime(datetime.fromisoformat(p.get("date","")))
        except Exception:
            pubdate = p.get("date","")
        rss.append(
            f"<item><title><![CDATA[{p.get('title','Untitled')}]]></title>"
            f"<link>{loc}</link>"
            f"<pubDate>{pubdate}</pubDate>"
            f"<description><![CDATA[{p.get('description','')}]]></description></item>"
        )
    rss.append("</channel></rss>")
    write_text(ROOT / "rss.xml", "\n".join(rss))
    print("✅ Rebuilt sitemap.xml & rss.xml")

# --- Build tag pages ---
def build_tags():
    posts = STATE.get("posts", [])
    tags = defaultdict(list)
    for p in posts:
        for t in p.get("tags", []):
            if isinstance(t, str) and t.strip():
                tags[t.strip()].append(p)

    for tag, arr in tags.items():
        out = ROOT / "tags" / tag / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        soup = BeautifulSoup("<html><body><h1>Tag: "+tag+"</h1><div id='list'></div></body></html>", "html.parser")
        list_div = soup.find(id="list")
        if list_div:
            list_div.clear()
        for p in arr:
            item = soup.new_tag("div", attrs={"class": "article-card"})
            href = f"{BASE}{p['url']}"
            a = soup.new_tag("a", href=href)
            a.string = p.get("title", "Untitled")
            meta = soup.new_tag("div", attrs={"class": "meta"})
            meta.string = p.get("date", "")
            desc = soup.new_tag("p")
            desc.string = p.get("description", "")
            item.append(a); item.append(meta); item.append(desc)
            list_div.append(item)
        write_text(out, str(soup))
    print("✅ Rebuilt tag pages")

# --- Fix meta[name=site-base] ---
def fix_root_shells():
    for fname in ["index.html", "search.html", "privacy.html", "terms.html", "404.html"]:
        path = ROOT / fname
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        head = soup.find("head")
        if head:
            meta = soup.find("meta", {"name":"site-base"})
            if not meta:
                meta = soup.new_tag("meta", attrs={"name":"site-base", "content": BASE})
                head.append(meta)
            else:
                meta["content"] = BASE
        path.write_text(str(soup), encoding="utf-8")
    print("✅ Fixed root shells (meta site-base)")

if __name__ == "__main__":
    normalize_state()
    build_main()
    build_sitemap_and_rss()
    build_tags()
    fix_root_shells()
    print("🏁 Rebuild finished")
