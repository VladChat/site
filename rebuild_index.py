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
