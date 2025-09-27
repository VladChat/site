import json, pathlib, datetime
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent
STATE = json.loads((ROOT / "data" / "state.json").read_text(encoding="utf-8"))
SITE = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["site"]
INDEX_TPL = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
TAG_TPL = (ROOT / "templates" / "tag.html").read_text(encoding="utf-8")

def write(path, txt):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

def build_index():
    # Render simple list into root index.html (already has shell)
    items = STATE.get("posts", [])[:50]
    # Also write feeds/search.json
    (ROOT / "feeds" / "search.json").write_text(json.dumps(items, indent=2), encoding="utf-8")

    # Patch into existing index.html
    home_path = ROOT / "index.html"
    soup = BeautifulSoup(home_path.read_text(encoding="utf-8"), "html.parser")
    list_div = soup.find(id="list")
    list_div.clear()
    for p in items:
        item = soup.new_tag("div", attrs={"class":"article-card"})
        a = soup.new_tag("a", href=p["url"])
        a.string = p["title"]
        meta = soup.new_tag("div", attrs={"class":"meta"}); meta.string = p["date"]
        desc = soup.new_tag("p"); desc.string = p.get("description","")
        item.append(a); item.append(meta); item.append(desc)
        list_div.append(item)
    home_path.write_text(str(soup), encoding="utf-8")

def build_sitemap_and_rss():
    base = SITE["base_url"].rstrip("/")
    posts = STATE.get("posts", [])[:500]
    # sitemap
    urls = ["<?xml version='1.0' encoding='UTF-8'?>",
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"]
    for p in posts:
        urls.append(f"  <url><loc>{base}{p['url']}</loc><lastmod>{p['date']}</lastmod></url>")
    urls.append("</urlset>")
    write(ROOT / "feeds" / "sitemap.xml", "\n".join(urls))

    # rss
    rss = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<rss version='2.0'><channel>",
           f"<title>{SITE.get('name','Blog')}</title>",
           f"<link>{base}</link>",
           "<description>Automated blog feed</description>"]
    for p in posts[:50]:
        rss.append(f"<item><title><![CDATA[{p['title']}]]></title><link>{base}{p['url']}</link><pubDate>{p['date']}</pubDate><description><![CDATA[{p.get('description','')}]]></description></item>")
    rss.append("</channel></rss>")
    write(ROOT / "feeds" / "rss.xml", "\n".join(rss))

def build_tags():
    # From posts metadata tags
    from collections import defaultdict
    by_tag = defaultdict(list)
    for p in STATE.get("posts", []):
        for t in p.get("tags", []):
            by_tag[t].append(p)
    for tag, items in by_tag.items():
        # Simple page
        html = TAG_TPL.replace("{{TAG}}", tag)
        path = ROOT / "tags" / tag / "index.html"
        soup = BeautifulSoup(html, "html.parser")
        list_div = soup.find(id="list"); list_div.clear()
        for p in items:
            item = soup.new_tag("div", attrs={"class":"article-card"})
            a = soup.new_tag("a", href=p["url"]); a.string = p["title"]
            meta = soup.new_tag("div", attrs={"class":"meta"}); meta.string = p["date"]
            desc = soup.new_tag("p"); desc.string = p.get("description","")
            item.append(a); item.append(meta); item.append(desc)
            list_div.append(item)
        write(path, str(soup))

if __name__ == "__main__":
    build_index()
    build_sitemap_and_rss()
    build_tags()
    print("Rebuilt index, sitemap, rss, tags")
