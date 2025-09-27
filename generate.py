import os, json, time, hashlib, re, argparse, datetime, pathlib, random
from urllib.parse import urlparse
import feedparser
from slugify import slugify
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

# OpenAI optional import (user must set OPENAI_API_KEY)
try:
    from openai import OpenAI
    _client = OpenAI()
except Exception:
    _client = None

ROOT = pathlib.Path(__file__).parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
STATE_PATH = ROOT / "data" / "state.json"
POSTS_JSON = STATE_PATH
POSTS_DIR = ROOT / "posts"
TEMPLATES = ROOT / "templates"
SITE = CONFIG.get("site", {})
MIN_WORDS = CONFIG.get("minWords", 1200)
MAX_WORDS = CONFIG.get("maxWords", 1400)

ENV = Environment(loader=FileSystemLoader([str(ROOT), str(ROOT / "templates")]))


def base_context(**extra):
    context = {
        "baseurl": CONFIG.get("baseurl", ""),
        "site": SITE,
        "config": CONFIG,
        "site_name": SITE.get("name", ""),
        "SITE_NAME": SITE.get("name", ""),
        "BYLINE": SITE.get("brand_byline", ""),
    }
    context.update(extra)
    return context

def read_state():
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({"seen_entries": [], "posts": []}, indent=2), encoding="utf-8")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))

def write_state(data):
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def fetch_news_items(hours=72, limit=20):
    items = []
    cutoff = time.time() - hours * 3600
    for url in CONFIG.get("rss_feeds", []):
        try:
            d = feedparser.parse(url)
            for e in d.entries[:50]:
                ts = None
                if hasattr(e, "published_parsed") and e.published_parsed:
                    ts = time.mktime(e.published_parsed)
                elif hasattr(e, "updated_parsed") and e.updated_parsed:
                    ts = time.mktime(e.updated_parsed)
                else:
                    ts = time.time()
                if ts >= cutoff:
                    items.append({
                        "title": getattr(e, "title", ""),
                        "summary": getattr(e, "summary", ""),
                        "link": getattr(e, "link", ""),
                        "source": urlparse(getattr(e, "link", "")).netloc or url
                    })
        except Exception as ex:
            print("Feed error:", url, ex)
    # Dedup by link
    seen = set()
    uniq = []
    for it in items:
        k = it.get("link") or it.get("title")
        if k not in seen:
            uniq.append(it)
            seen.add(k)
    random.shuffle(uniq)
    return uniq[:limit]

def build_prompt(keyword, news_batch):
    summaries = "\n".join([f"- {n['title']} — {n['source']}" for n in news_batch])
    return f"""You are an award-winning news/SEO writer.
Primary keyword: {keyword}
News signals (headlines & sources):
{summaries}

Write a long-form article (between {MIN_WORDS} and {MAX_WORDS} words) in six sections, with headings exactly:
1. Introduction
2. Background
3. Analysis
4. Impact
5. Takeaways
6. Sources

Rules:
- Mention the keyword in the intro, in at least one H2, and in the conclusion.
- Use clear subheads and short paragraphs.
- Include bullet points where useful.
- Provide 3–6 external sources in "Sources".
- Keep tone helpful and credible.
"""

def call_openai(prompt):
    if _client is None:
        # Fallback dummy content for environments without API
        body = """# Introduction
This is demo content. Replace with OpenAI output.

# Background
...

# Analysis
...

# Impact
...

# Takeaways
- point
- point

# Sources
- https://example.com
"""
        return body
    model = CONFIG.get("model", "gpt-5-mini")
    try:
        # Try Chat Completions
        resp = _client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":"You write structured, factual, SEO-friendly articles."},
                      {"role":"user","content": prompt}],
            temperature=0.4
        )
        return resp.choices[0].message.content
    except Exception as ex:
        # Try Responses API if available
        try:
            resp = _client.responses.create(model=model, input=prompt)
            return resp.output_text
        except Exception as ex2:
            print("OpenAI error:", ex2)
            raise

def render_post(title, html_body, date, description):
    related = ENV.get_template("partials/related.html").render(base_context())
    faq = ENV.get_template("partials/faq.html").render(base_context())

    # Estimate reading time ~200 wpm
    words = len(re.sub(r"<[^>]+>", " ", html_body).split())
    minutes = max(1, int(words / 200))
    reading_time = f"~{minutes} min read"

    post_context = base_context(
        POST_TITLE=title,
        DATE=date.strftime("%B %d, %Y"),
        READING_TIME=reading_time,
        POST_BODY=html_body,
        RELATED=related,
        FAQ=faq,
    )
    post_html = ENV.get_template("post.html").render(post_context)

    canonical = f"{CONFIG['site']['base_url'].rstrip('/')}/posts/{date:%Y/%m/%d}/{slugify(title)}.html"
    head_context = base_context(
        TITLE=title,
        DESCRIPTION=description,
        PUBLISHED_ISO=date.isoformat(),
        UPDATED_ISO=date.isoformat(),
        BYLINE=SITE.get('brand_byline',''),
        SITE_NAME=SITE.get('name',''),
        CANONICAL=canonical,
    )
    head_filled = ENV.get_template("partials/head-meta.html").render(head_context)

    layout_context = base_context(
        LANG=SITE.get('language','en'),
        TITLE=title,
        DESCRIPTION=description,
        HEAD_META=head_filled,
        SITE_NAME=SITE.get('name','Vlad’s Blog'),
        BYLINE=SITE.get('brand_byline',''),
        CONTENT=post_html,
    )
    final_html = ENV.get_template("layout.html").render(layout_context)
    return final_html

def md_to_html(md_text):
    # Minimal markdown -> HTML for headings & lists
    html = md_text
    html = re.sub(r"^# (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)  # top-level as H2 inside article
    html = re.sub(r"^## (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(?:<li>.*</li>\n?)+", lambda m: "<ul>" + m.group(0).replace("\n","") + "</ul>", html)
    html = re.sub(r"\n\n", r"</p><p>", html)
    html = "<p>" + html + "</p>"
    return html


def render_index_page():
    template = ENV.get_template("index.html")
    html = template.render(base_context())
    (ROOT / "index.html").write_text(html, encoding="utf-8")


def render_static_pages():
    for page in ["privacy.html", "terms.html", "search.html", "404.html"]:
        template = ENV.get_template(page)
        html = template.render(base_context())
        (ROOT / page).write_text(html, encoding="utf-8")


def main(auto=False):
    state = read_state()
    news = fetch_news_items(hours=CONFIG.get("horizonHours",72), limit=12)
    if not news:
        news = [{"title":"Travel demand is rising","source":"example.com","link":"#","summary":""}]
    kw = random.choice(CONFIG.get("keywords", ["travel"]))
    prompt = build_prompt(kw, news[:6])
    body = call_openai(prompt)
    # Extract title as first non-empty line or fall back
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    title = lines[0][:100] if lines else f"Trends in {kw}"
    # Convert to rudimentary HTML
    html_body = md_to_html(body)
    # Description from first paragraph
    soup = BeautifulSoup(html_body, "html.parser")
    first_p = soup.find("p")
    description = (first_p.get_text()[:160] if first_p else f"Insights on {kw}").strip()

    # Path setup
    now = datetime.date.today()
    slug = slugify(title) or f"post-{int(time.time())}"
    out_dir = ROOT / "posts" / now.strftime("%Y/%m/%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.html"

    final_html = render_post(title, html_body, now, description)
    out_path.write_text(final_html, encoding="utf-8")

    # Update state posts list
    post_url = f"/posts/{now:%Y/%m/%d}/{slug}.html"
    meta = {"title": title, "url": post_url, "date": now.isoformat(), "description": description, "tags": ["travel"]}
    state.setdefault("posts", []).insert(0, meta)
    write_state(state)

    print("Wrote", out_path)

    # Refresh shared pages with resolved template context
    render_index_page()
    render_static_pages()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="Run in auto mode")
    args = ap.parse_args()
    main(auto=args.auto)
