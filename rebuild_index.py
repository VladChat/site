import json
import math
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

ROOT = Path(__file__).resolve().parent

def read_json(rel: str, default=None):
    p = ROOT / rel
    if not p.exists():
        return {} if default is None else default
    try:
        return json.loads(p.read_text(encoding="utf-8")) or ({} if default is None else default)
    except Exception:
        return {} if default is None else default

def write_text(path: Path, txt: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

# --- Load site config/state ---
CFG_ALL = read_json("config/config.json", {})
SITE = CFG_ALL.get("site", {}) or {}
BASE = (SITE.get("base_url") or "").rstrip("/")
SITE_URL = (SITE.get("url") or "").rstrip("/")
POSTS_PER_PAGE = int(SITE.get("posts_per_page", 20))
STATE = read_json("data/state.json", {})
STATE_PATH = ROOT / "data/state.json"

# --- Normalize state (URLs, dedup) ---
def normalize_state():
    posts = list(STATE.get("posts") or [])
    seen = set()
    out = []
    changed = False
    for p in posts:
        item = dict(p)
        url = (item.get("url") or "").strip()
        orig = url

        if url and not url.startswith(("/", "http://", "https://")):
            url = "/" + url
        if url.startswith("/site/site/"):
            url = url[len("/site"):]
        if BASE and url.startswith(BASE + "/"):
            url = url[len(BASE):]
        if url.startswith("/site/posts/"):
            url = url[len("/site"):]

        if url != orig:
            changed = True
        item["url"] = url

        key = (item.get("title",""), item.get("date",""), item["url"])
        if key in seen:
            changed = True
            continue
        seen.add(key)
        out.append(item)

    if changed:
        STATE["posts"] = out
        STATE_PATH.write_text(json.dumps(STATE, ensure_ascii=False, indent=2), encoding="utf-8")
        print("🧹 Normalized data/state.json")

# --- Helpers to find/prepare containers safely ---
def _load_index_base():
    """
    Всегда используем текущий корневой index.html как базу (с твоей версткой и стилями).
    Если его нет — падаем обратно на templates/index.html.
    """
    base = ROOT / "index.html"
    if base.exists():
        return base.read_text(encoding="utf-8")
    tpl = ROOT / "templates" / "index.html"
    return tpl.read_text(encoding="utf-8") if tpl.exists() else "<!doctype html><html><head><meta charset='utf-8'><title>Latest posts</title></head><body><h1>Latest posts</h1><div id='list'></div></body></html>"

def _ensure_list_container(soup: BeautifulSoup):
    cnt = soup.find(id="list")
    if cnt is None:
        # Создадим контейнер в конце body
        body = soup.find("body") or soup
        cnt = soup.new_tag("div", id="list")
        body.append(cnt)
    else:
        cnt.clear()
    return cnt

def _ensure_pager_container(soup: BeautifulSoup):
    pg = soup.find(id="pager")
    if pg is None:
        body = soup.find("body") or soup
        pg = soup.new_tag("nav", id="pager")
        body.append(pg)
    else:
        pg.clear()
    return pg

# --- Build paginated index pages preserving layout ---
def build_main_and_pages():
    posts = list(STATE.get("posts") or [])
    total = len(posts)
    pages = max(1, math.ceil(total / POSTS_PER_PAGE))

    base_html = _load_index_base()

    for page in range(1, pages + 1):
        start = (page - 1) * POSTS_PER_PAGE
        end = start + POSTS_PER_PAGE
        chunk = posts[start:end]

        soup = BeautifulSoup(base_html, "html.parser")
        lst = _ensure_list_container(soup)

        # Рендер карточек (минимальная разметка — твои стили её «подцепят»)
        for p in chunk:
            a = soup.new_tag("a", href=f"{SITE_URL}{BASE}{p['url']}")
            a.string = p.get("title") or "Untitled"
            date = soup.new_tag("div", **{"class": "meta"})
            date.string = p.get("date", "")
            desc = soup.new_tag("p")
            desc.string = p.get("description","")
            card = soup.new_tag("article", **{"class": "post-card"})
            card.append(a); card.append(date); card.append(desc)
            lst.append(card)

        # Пагинация (если >1 страницы)
        pager = _ensure_pager_container(soup)
        if pages > 1:
            if page > 1:
                prev = soup.new_tag("a", href=f"{SITE_URL}{BASE}/page/{page-1}/")
                prev.string = "« Prev"
                pager.append(prev)
            # номера страниц
            for i in range(1, pages + 1):
                link = f"{SITE_URL}{BASE}/" if i == 1 else f"{SITE_URL}{BASE}/page/{i}/"
                a = soup.new_tag("a", href=link)
                a.string = str(i)
                if i == page:
                    a.attrs["aria-current"] = "page"
                pager.append(a)
            if page < pages:
                nxt = soup.new_tag("a", href=f"{SITE_URL}{BASE}/page/{page+1}/")
                nxt.string = "Next »"
                pager.append(nxt)
        else:
            pager.decompose()  # если одна страница — не показываем блок

        # Сохраняем
        out_path = ROOT / "index.html" if page == 1 else ROOT / "page" / str(page) / "index.html"
        write_text(out_path, str(soup))

    # Быстрый клиентский индекс для поиска (ограничим 200)
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    write_text(feeds_dir / "search.json", json.dumps(posts[:200], ensure_ascii=False, indent=2))
    print(f"✅ Rebuilt {pages} index pages with pagination (layout preserved)")

# --- Build sitemap & RSS ---
def build_sitemap_and_rss():
    posts = list(STATE.get("posts") or [])
    feeds_dir = ROOT / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)

    # sitemap.xml
    urls = [f"{SITE_URL}{BASE}{p['url']}" for p in posts]
    xml = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    xml += [f"<url><loc>{u}</loc></url>" for u in urls]
    xml.append("</urlset>")
    write_text(feeds_dir / "sitemap.xml", "\n".join(xml))

    # rss.xml
    rss = ["<?xml version='1.0' encoding='UTF-8'?>", "<rss version='2.0'><channel>"]
    rss.append(f"<title>{SITE.get('name','Blog')}</title>")
    rss.append(f"<link>{SITE_URL}{BASE}</link>")
    rss.append("<description>Automated blog feed</description>")
    for p in posts[:100]:
        link = f"{SITE_URL}{BASE}{p['url']}"
        title = (p.get("title") or "").replace("&","&amp;")
        desc = (p.get("description") or "").replace("&","&amp;")
        pub = p.get("date") or datetime.utcnow().strftime("%Y-%m-%d")
        rss.append(f"<item><title><![CDATA[{title}]]></title><link>{link}</link><pubDate>{pub}</pubDate><description><![CDATA[{desc}]]></description></item>")
    rss.append("</channel></rss>")
    write_text(feeds_dir / "rss.xml", "\n".join(rss))
    print("🗺️ sitemap.xml & 📰 rss.xml rebuilt")

# --- Keep meta site-base on existing shells (no changes otherwise) ---
def fix_root_shells():
    for rel in ["index.html","search.html","privacy.html","terms.html","404.html"]:
        path = ROOT / rel
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        head = soup.find("head") or soup
        meta = head.find("meta", attrs={"name": "site-base"})
        content_val = f"{SITE_URL}{BASE}"
        if not meta:
            meta = soup.new_tag("meta", attrs={"name": "site-base", "content": content_val})
            head.append(meta)
        else:
            meta["content"] = content_val
        path.write_text(str(soup), encoding="utf-8")
    print("✅ Root shells checked (meta site-base)")

if __name__ == "__main__":
    normalize_state()
    build_main_and_pages()
    build_sitemap_and_rss()
    fix_root_shells()
    print("🏁 Rebuild finished")
