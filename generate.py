import os, json, time, hashlib, re, argparse, datetime, pathlib, random
from urllib.parse import urlparse
import feedparser
from slugify import slugify
from bs4 import BeautifulSoup
from jinja2 import Template

try:
    from openai import OpenAI
    _client = OpenAI()
except Exception:
    _client = None

ROOT = pathlib.Path(__file__).parent

def load_json(filename):
    return json.loads((ROOT / filename).read_text(encoding='utf-8'))

# read from /config
CONFIG = load_json('config/config.json')
KEYWORDS = load_json('config/keywords.json')['keywords']
FEEDS = load_json('config/feeds.json')['rss_feeds']
ADS = load_json('config/ads.json')
ANALYTICS = load_json('config/analytics.json')

try:
    WRITER = load_json('config/writer.json')
except Exception:
    WRITER = {}

STATE_PATH = ROOT / 'data' / 'state.json'
POSTS_DIR = ROOT / 'posts'
TEMPLATES = ROOT / 'templates'
SITE = CONFIG.get('site', {})
MIN_WORDS = WRITER.get('minWords', CONFIG.get('minWords', 1200))
MAX_WORDS = WRITER.get('maxWords', CONFIG.get('maxWords', 1400))

SECTIONS = WRITER.get('sections', ['Introduction','Background','Analysis','Impact','Takeaways','Sources'])

def read_state():
    if not STATE_PATH.exists():
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps({'seen_entries': [], 'posts': []}, indent=2), encoding='utf-8')
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))

def write_state(data):
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')

def fetch_news_items(hours=72, limit=20):
    items = []
    cutoff = time.time() - hours * 3600
    for url in FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:50]:
                if hasattr(e, 'published_parsed') and e.published_parsed:
                    ts = time.mktime(e.published_parsed)
                elif hasattr(e, 'updated_parsed') and e.updated_parsed:
                    ts = time.mktime(e.updated_parsed)
                else:
                    ts = time.time()
                if ts >= cutoff:
                    items.append({
                        'title': getattr(e, 'title', ''),
                        'summary': getattr(e, 'summary', ''),
                        'link': getattr(e, 'link', ''),
                        'source': urlparse(getattr(e, 'link', '')).netloc or url
                    })
        except Exception as ex:
            print('Feed error:', url, ex)
    seen = set(); uniq = []
    for it in items:
        k = it.get('link') or it.get('title')
        if k not in seen:
            uniq.append(it); seen.add(k)
    random.shuffle(uniq)
    return uniq[:limit]


def build_prompt(keyword, news_batch):
    summaries = '\n'.join([f"- {n.get('title','')} — {n.get('source','')}" for n in news_batch])
    # Writer config templating
    prompt_cfg = WRITER.get('prompt', {})
    tpl_user = prompt_cfg.get('user')
    sections_enum = "\n".join([f"{i+1}. {s}" for i, s in enumerate(SECTIONS)])
    sections_md = "\n".join([f"## {s}" for s in SECTIONS])
    ctx = {
        'keyword': keyword,
        'summaries': summaries,
        'MIN_WORDS': MIN_WORDS,
        'MAX_WORDS': MAX_WORDS,
        'SECTIONS': SECTIONS,
        'SECTIONS_ENUM': sections_enum,
        'SECTIONS_MD': sections_md
    }
    if tpl_user:
        try:
            return prompt_cfg.get('system', ''), tpl_user.format(**ctx)
        except Exception as ex:
            print('writer.json user template format error:', ex)
    # Fallback to built-in prompt
    user_prompt = f"""You are an award-winning news/SEO writer.
Primary keyword: {keyword}
News signals (headlines & sources):
{summaries}

Write a long-form article (between {MIN_WORDS} and {MAX_WORDS} words) with section headings exactly:
{sections_enum}

Rules:
- Mention the keyword in the intro, in at least one H2, and in the conclusion.
- Use clear subheads and short paragraphs.
- Include bullet points where useful.
- Provide 3–6 external sources in 'Sources' as plain links.
"""
    system_prompt = prompt_cfg.get('system', 'You write structured, factual, SEO-friendly articles.')
    return system_prompt, user_prompt



def call_openai(user_prompt, system_prompt=None):
    # Demo fallback
    if _client is None:
        body = "# " + SECTIONS[0] + "\nThis is demo content. Replace with OpenAI output.\n\n" +                "\n\n".join([f"# {s}\n..." for s in SECTIONS[1:-1]]) +                "\n\n# " + SECTIONS[-1] + "\n- https://example.com"
        return body
    model = WRITER.get('model', CONFIG.get('model', 'gpt-5-mini'))
    temperature = WRITER.get('temperature', 0.4)
    messages = []
    messages.append({'role':'system','content': system_prompt or 'You write structured, factual, SEO-friendly articles.'})
    messages.append({'role':'user','content': user_prompt})
    try:
        resp = _client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature
        )
        return resp.choices[0].message.content
    except Exception as ex:
        # Try fallback model if specified
        fb = WRITER.get('fallbackModel', CONFIG.get('fallback_model'))
        if fb:
            try:
                resp = _client.chat.completions.create(
                    model=fb,
                    messages=messages,
                    temperature=temperature
                )
                return resp.choices[0].message.content
            except Exception as ex2:
                print('OpenAI fallback error:', ex2)
        # As last resort try Responses API
        try:
            resp = _client.responses.create(model=model, input=user_prompt)
            return resp.output_text
        except Exception as ex3:
            print('OpenAI error:', ex3)
            raise


def render_post(title, html_body, date, description):
    layout = (TEMPLATES / 'layout.html').read_text(encoding='utf-8')
    post_tpl = (TEMPLATES / 'post.html').read_text(encoding='utf-8')
    head_meta = (TEMPLATES / 'partials' / 'head-meta.html').read_text(encoding='utf-8')
    related = (TEMPLATES / 'partials' / 'related.html').read_text(encoding='utf-8')
    faq = (TEMPLATES / 'partials' / 'faq.html').read_text(encoding='utf-8')

    words = len(re.sub(r'<[^>]+>', ' ', html_body).split())
    minutes = max(1, int(words / 200))
    reading_time = f'~{minutes} min read'

    from jinja2 import Template
    post_html = Template(post_tpl).render(
        POST_TITLE=title, DATE=date.strftime('%B %d, %Y'), READING_TIME=reading_time,
        POST_BODY=html_body, RELATED=related, FAQ=faq
    )

    canonical = f"{SITE['base_url'].rstrip('/')}/posts/{date:%Y/%m/%d}/{slugify(title)}.html"
    head_filled = Template(head_meta).render(
        TITLE=title, DESCRIPTION=description, PUBLISHED_ISO=date.isoformat(), UPDATED_ISO=date.isoformat(),
        BYLINE=SITE.get('brand_byline',''), SITE_NAME=SITE.get('name',''),
        CANONICAL=canonical
    )

    final_html = Template(layout).render(
        LANG=SITE.get('language','en'), BASEURL=SITE.get('base_url','').rstrip('/'),
        TITLE=title, DESCRIPTION=description, HEAD_META=head_filled,
        SITE_NAME=SITE.get('name','uPatch Blog'), BYLINE=SITE.get('brand_byline',''),
        CONTENT=post_html
    )
    return final_html

def md_to_html(md_text):
    html = md_text
    import re
    html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(?:<li>.*</li>\n?)+', lambda m: '<ul>' + m.group(0).replace('\n','') + '</ul>', html)
    html = re.sub(r'\n\n', r'</p><p>', html)
    html = '<p>' + html + '</p>'
    return html

def main(auto=False):
    state = read_state()
    news = fetch_news_items(hours=CONFIG.get('horizonHours',72), limit=12)
    if not news:
        news = [{'title':'Travel demand is rising','source':'example.com','link':'#','summary':''}]
    kw = random.choice(KEYWORDS)
    system_prompt, user_prompt = build_prompt(kw, news[:6])
    body = call_openai(user_prompt, system_prompt)

    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    title = lines[0][:100] if lines else f'Trends in {kw}'

    html_body = md_to_html(body)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_body, 'html.parser')
    first_p = soup.find('p')
    description = (first_p.get_text()[:160] if first_p else f'Insights on {kw}').strip()

    now = datetime.date.today()
    slug = slugify(title) or f'post-{int(time.time())}'
    out_dir = ROOT / 'posts' / now.strftime('%Y/%m/%d')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{slug}.html'

    final_html = render_post(title, html_body, now, description)
    out_path.write_text(final_html, encoding='utf-8')

    post_url = f'/posts/{now:%Y/%m/%d}/{slug}.html'
    meta = {'title': title, 'url': post_url, 'date': now.isoformat(), 'description': description, 'tags': ['travel']}
    state.setdefault('posts', []).insert(0, meta)
    write_state(state)

    print('Wrote', out_path)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--auto', action='store_true', help='Run in auto mode')
    args = ap.parse_args()
    main(auto=args.auto)
