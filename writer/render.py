import re
from html import escape
from datetime import datetime

def md_to_html(md: str) -> str:
    lines = [l.rstrip() for l in md.strip().splitlines() if l.strip()]
    html_lines, in_ul = [], False
    for ln in lines:
        if ln.startswith("# "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h2>{ln[2:].strip()}</h2>")
        elif ln.startswith("## "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<h3>{ln[3:].strip()}</h3>")
        elif ln.startswith("- "):
            if not in_ul: html_lines.append("<ul>"); in_ul = True
            html_lines.append(f"<li>{ln[2:].strip()}</li>")
        else:
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(f"<p>{ln}</p>")
    if in_ul: html_lines.append("</ul>")
    return "\n".join(html_lines)

def slugify(s: str) -> str:
    return re.sub(r'[^a-z0-9\-]+', '-', s.lower()).strip('-')

def plain_text(s: str) -> str:
    s = re.sub(r"^#\s+", "", s, flags=re.M)
    s = re.sub(r"^-\s+", "", s, flags=re.M)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def render_post_html(title, body_md, faq_html, faq_jsonld, configs, *, slug, published_at=None):
    ROOT = configs["root"]
    with open(f"{ROOT}/templates/layout.html", encoding="utf-8") as f:
        layout = f.read()
    with open(f"{ROOT}/templates/post.html", encoding="utf-8") as f:
        post_tpl = f.read()
    with open(f"{ROOT}/templates/partials/head-meta.html", encoding="utf-8") as f:
        head_meta = f.read()

    published_at = published_at or datetime.today()
    words = len(re.findall(r"\w+", body_md))
    reading_time = f"{max(1, words // 200)} min read"
    site = configs["base_config"]["site"]
    site_name = site.get("name", "")

    # берём домен и base_url из конфига
    site_url = site.get("url", "").rstrip("/")
    base_url = site.get("base_url", "").rstrip("/")

    body_html = md_to_html(body_md)
    content = (post_tpl
        .replace("{{POST_TITLE}}", title)
        .replace("{{DATE}}", published_at.strftime("%Y-%m-%d"))
        .replace("{{READING_TIME}}", reading_time)
        .replace("{{POST_BODY}}", body_html)
        .replace("{{RELATED}}", "")
        .replace("{{FAQ}}", faq_html)
    )

    # формируем полный каноникал
    canonical_url = (
        f"{site_url}{base_url}/posts/"
        f"{published_at.year:04d}/{published_at.month:02d}/{published_at.day:02d}/{slug}.html"
    )

    description = plain_text(body_md)[:160]
    page_title = f"{title} — {site_name}" if site_name else title
    head_filled = (head_meta
        .replace("{{TITLE}}", title)
        .replace("{{DESCRIPTION}}", description)
        .replace("{{CANONICAL}}", canonical_url)
        .replace("{{PUBLISHED_ISO}}", published_at.strftime("%Y-%m-%d"))
        .replace("{{UPDATED_ISO}}", published_at.strftime("%Y-%m-%d"))
        .replace("{{BYLINE}}", site.get("brand_byline",""))
        .replace("{{SITE_NAME}}", site.get("name",""))
    ) + "\n" + faq_jsonld

    if "{{ head_meta }}" in layout:
        layout = layout.replace("{{ head_meta }}", head_filled)
    else:
        layout = layout.replace("</head>", head_filled + "\n</head>")

    layout = layout.replace("{{ page_title }}", page_title)
    layout = layout.replace("{{ page_description }}", escape(description, quote=True))
    layout = layout.replace("{{ site.name }}", site_name)
    layout = layout.replace("{{ content }}", content)

    return layout
