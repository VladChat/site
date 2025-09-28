import json, pathlib, datetime
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent

def load_json(filename):
    return json.loads((ROOT / filename).read_text(encoding='utf-8'))

STATE = load_json('data/state.json')
SITE = load_json('config/config.json')['site']
INDEX_TPL = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')
TAG_TPL = (ROOT / 'templates' / 'tag.html').read_text(encoding='utf-8')

def _prefix_urls(soup, base):
    for tag in soup.find_all(True):
        for attr in ('href', 'src'):
            if tag.has_attr(attr):
                v = tag.get(attr, '')
                if isinstance(v, str) and v.startswith('/'):
                    tag[attr] = base.rstrip('/') + v
    head = soup.find('head')
    if head:
        mb = head.find('meta', attrs={'name':'site-base'})
        if mb:
            mb['content'] = base.rstrip('/')
        else:
            m = soup.new_tag('meta')
            m.attrs['name'] = 'site-base'
            m.attrs['content'] = base.rstrip('/')
            head.append(m)

def write(path, txt):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding='utf-8')

def build_index():
    items = STATE.get('posts', [])[:50]
    (ROOT / 'feeds').mkdir(parents=True, exist_ok=True)
    (ROOT / 'feeds' / 'search.json').write_text(json.dumps(items, indent=2), encoding='utf-8')

    home_path = ROOT / 'index.html'
    soup = BeautifulSoup(home_path.read_text(encoding='utf-8'), 'html.parser')
    list_div = soup.find(id='list')
    if list_div:
        list_div.clear()
    base = SITE['base_url'].rstrip('/')
    for p in items:
        item = soup.new_tag('div', attrs={'class': 'article-card'})
        # url всегда чистый (/posts/...), добавляем base один раз
        a = soup.new_tag('a', href=f"{base}{p['url']}")
        a.string = p['title']
        meta = soup.new_tag('div', attrs={'class': 'meta'})
        meta.string = p['date']
        desc = soup.new_tag('p')
        desc.string = p.get('description', '')
        item.append(a)
        item.append(meta)
        item.append(desc)
        if list_div:
            list_div.append(item)
    home_path.write_text(str(soup), encoding='utf-8')

def build_sitemap_and_rss():
    base = SITE['base_url'].rstrip('/')
    posts = STATE.get('posts', [])[:500]

    urls = ["<?xml version='1.0' encoding='UTF-8'?>",
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for p in posts:
        urls.append(f"  <url><loc>{base}{p['url']}</loc><lastmod>{p['date']}</lastmod></url>")
    urls.append('</urlset>')
    write(ROOT / 'feeds' / 'sitemap.xml', "\n".join(urls))

    rss = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<rss version='2.0'><channel>",
           f"<title>{SITE.get('name','Blog')}</title>",
           f"<link>{base}</link>",
           "<description>Automated blog feed</description>"]
    for p in posts[:50]:
        rss.append(
            f"<item><title><![CDATA[{p['title']}]]></title>"
            f"<link>{base}{p['url']}</link>"
            f"<pubDate>{p['date']}</pubDate>"
            f"<description><![CDATA[{p.get('description','')}]]></description></item>"
        )
    rss.append('</channel></rss>')
    write(ROOT / 'feeds' / 'rss.xml', "\n".join(rss))

def build_tags():
    from collections import defaultdict
    by_tag = defaultdict(list)
    for p in STATE.get('posts', []):
        for t in p.get('tags', []):
            by_tag[t].append(p)
    base = SITE['base_url'].rstrip('/')
    for tag, items in by_tag.items():
        html = TAG_TPL.replace('{{TAG}}', tag)
        path = ROOT / 'tags' / tag / 'index.html'
        soup = BeautifulSoup(html, 'html.parser')
        list_div = soup.find(id='list')
        if list_div:
            list_div.clear()
        for p in items:
            item = soup.new_tag('div', attrs={'class': 'article-card'})
            a = soup.new_tag('a', href=f"{base}{p['url']}")
            a.string = p['title']
            meta = soup.new_tag('div', attrs={'class': 'meta'})
            meta.string = p['date']
            desc = soup.new_tag('p')
            desc.string = p.get('description', '')
            item.append(a)
            item.append(meta)
            item.append(desc)
            if list_div:
                list_div.append(item)
        write(path, str(soup))

def fix_root_shells():
    pages = ['index.html', 'privacy.html', 'terms.html', 'search.html', '404.html']
    base = SITE['base_url'].rstrip('/')
    for name in pages:
        path = ROOT / name
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        _prefix_urls(soup, base)
        path.write_text(str(soup), encoding='utf-8')

if __name__ == '__main__':
    build_index()
    build_sitemap_and_rss()
    build_tags()
    fix_root_shells()
    print('Rebuilt index, sitemap, rss, tags, and fixed root shells')
# rebuild_index.py
import os, json, re
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime

ROOT = Path(__file__).resolve().parent

def read_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

def write_text(path: Path, txt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

# --- Load site + state ---
SITE_ALL = read_json("config/config.json")
SITE = SITE_ALL.get("site", {})
BASE = SITE.get("base_url", "").rstrip("/")            # например: "/site" или ""
SITE_URL = SITE.get("url", "").rstrip("/")             # например: "https://vladchat.github.io"

STATE_PATH = ROOT / "data/state.json"
STATE = read_json("data/state.json")

# --- Normalize state: ensure p['url'] is ALWAYS "/posts/....html" (no /site prefix) ---
def normalize_state():
    changed = False
    posts = STATE.get("posts", [])
    norm_posts = []
    seen = set()

    for p in posts:
        url_orig = p.get("url", "") or ""
        url = url_orig

        # ensure leading slash for relative local URLs
        if url and not url.startswith(("http://", "https://", "/")):
            url = "/" + url

        # collapse accidental double "/site/site/..."
        if url.startswith("/site/site/"):
            url = url[len("/site"):]  # -> "/site/..."

        # strip BASE from the start (e.g. "/site/posts/..." -> "/posts/...")
        if BASE and url.startswith(BASE + "/"):
            url = url[len(BASE):]

        # if somehow still "/site/posts/..." (BASE could be empty), strip the literal
        if url.startswith("/site/posts/"):
            url = url[len("/site"):]  # -> "/posts/..."

        # now enforce that blog URLs are stored as "/posts/..."
        # (if it's not a blog URL, leave as is; but our generator stores only posts)
        # just make sure it starts with '/'
        if url and not url.startswith(("/", "http://", "https://")):
            url = "/" + url

        if url != url_orig:
            changed = True
        p["url"] = url

        key = (p.get("title",""), p.get("date",""), p["url"])
        if key not in seen:
            norm_posts.append(p)
            seen.add(key)
        else:
            changed = True  # drop duplicates

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

    base = BASE  # prefix once
    for p in posts:
        item = soup.new_tag("div", attrs={"class": "article-card"})

        href = f"{base}{p['url']}" if isinstance(p.get("url"), str) else "#"
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
    # also write feeds/search.json for client search
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    write_text(feeds_dir / "search.json", json.dumps(STATE.get("posts", [])[:200], ensure_ascii=False, indent=2))
    print("✅ Rebuilt main index.html + feeds/search.json")

# --- Build sitemap.xml & rss.xml ---
def build_sitemap_and_rss():
    posts = STATE.get("posts", [])[:500]
    base = BASE
    site_url = SITE_URL

    # sitemap.xml
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in posts:
        loc = f"{site_url}{base}{p['url']}" if site_url else f"{base}{p['url']}"
        lastmod = p.get("date", "")
        sitemap.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
    sitemap.append("</urlset>")
    write_text(ROOT / "sitemap.xml", "\n".join(sitemap))

    # rss.xml
    rss = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0"><channel>',
           f"<title>{SITE.get('name','Blog')}</title>",
           f"<link>{site_url}{base}/</link>" if site_url else f"<link>{base}/</link>",
           f"<description>{SITE.get('name','Automated Blog')}</description>"]
    for p in posts[:50]:
        loc = f"{site_url}{base}{p['url']}" if site_url else f"{base}{p['url']}"
        # pubDate in RFC-2822
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
    from collections import defaultdict
    posts = STATE.get("posts", [])
    tags = defaultdict(list)
    for p in posts:
        for t in p.get("tags", []):
            if isinstance(t, str) and t.strip():
                tags[t.strip()].append(p)

    base = BASE
    for tag, arr in tags.items():
        out = ROOT / "tags" / tag / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        soup = BeautifulSoup("<html><body><h1>Tag: "+tag+"</h1><div id='list'></div></body></html>", "html.parser")
        list_div = soup.find(id="list")
        if list_div:
            list_div.clear()
        for p in arr:
            item = soup.new_tag("div", attrs={"class": "article-card"})
            href = f"{base}{p['url']}"
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

# --- Fix meta[name=site-base] in root shells (index/search/etc) ---
def fix_root_shells():
    base = BASE
    for fname in ["index.html", "search.html", "privacy.html", "terms.html", "404.html"]:
        path = ROOT / fname
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        head = soup.find("head")
        if head:
            meta = soup.find("meta", {"name":"site-base"})
            if not meta:
                meta = soup.new_tag("meta", attrs={"name":"site-base", "content": base})
                head.append(meta)
            else:
                meta["content"] = base
        path.write_text(str(soup), encoding="utf-8")
    print("✅ Fixed root shells (meta site-base)")

if __name__ == "__main__":
    normalize_state()           # << ключевая строка: чистим state.json от лишнего /site
    build_main()
    build_sitemap_and_rss()
    build_tags()
    fix_root_shells()
    print("🏁 Rebuild finished")
