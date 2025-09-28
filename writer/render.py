import re
from datetime import datetime
from pathlib import Path
from slugify import slugify as _slugify


def slugify(s: str) -> str:
    s = (s or "").strip()
    s = _slugify(s, lowercase=True) if s else "post"
    return re.sub(r"-{2,}", "-", s).strip("-") or "post"


def md_to_html(md: str) -> str:
    """Простенький конвертер Markdown → HTML (заголовки/списки/параграфы)."""
    if not md:
        return "<p></p>"
    lines = [l.rstrip() for l in md.splitlines()]
    html, in_ul = [], False
    for ln in lines:
        if not ln.strip():
            if in_ul:
                html.append("</ul>"); in_ul = False
            continue
        if ln.startswith("# "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h2>{ln[2:].strip()}</h2>")
        elif ln.startswith("## "):
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<h3>{ln[3:].strip()}</h3>")
        elif ln.startswith("- "):
            if not in_ul:
                html.append("<ul>"); in_ul = True
            html.append(f"<li>{ln[2:].strip()}</li>")
        else:
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<p>{ln}</p>")
    if in_ul: html.append("</ul>")
    return "\n".join(html)


def plain_text(html: str) -> str:
    # Быстрый срез тегов
    txt = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", txt).strip()


def render_post_html(title: str, body_md: str, faq_html: str, faq_jsonld: str, configs: dict) -> str:
    root = Path(configs.get("root") or ".").resolve()
    site = configs.get("base_config", {}).get("site", {})
    site_name = site.get("name", "uPatch Blog")
    base_url = (site.get("base_url") or "").rstrip("/")
    site_url = (site.get("url") or "").rstrip("/")

    # Загружаем шаблоны
    layout = (root / "templates" / "layout.html").read_text(encoding="utf-8")
    post_tpl = (root / "templates" / "post.html").read_text(encoding="utf-8")
    head_meta_tpl = (root / "templates" / "partials" / "head-meta.html").read_text(encoding="utf-8")

    today = datetime.now()
    # Итоговый относительный путь поста (без base_url)
    rel_url = f"/posts/{today.year:04d}/{today.month:02d}/{today.day:02d}/{slugify(title)}.html"
    canonical_url = f"{site_url}{base_url}{rel_url}"

    body_html = md_to_html(body_md or "")
    content = (post_tpl
               .replace("{{POST_TITLE}}", title)
               .replace("{{DATE}}", today.strftime("%Y-%m-%d"))
               .replace("{{READING_TIME}}", "7 min read")
               .replace("{{POST_BODY}}", body_html)
               .replace("{{FAQ}}", faq_html or "")
               .replace("{{RELATED}}", ""))

    description = plain_text(body_html)[:160]

    head_filled = (head_meta_tpl
                   .replace("{{TITLE}}", title)
                   .replace("{{DESCRIPTION}}", description)
                   .replace("{{CANONICAL}}", canonical_url)
                   .replace("{{PUBLISHED_ISO}}", today.strftime("%Y-%m-%d"))
                   .replace("{{UPDATED_ISO}}", today.strftime("%Y-%m-%d"))
                   .replace("{{BYLINE}}", site.get("brand_byline", ""))
                   .replace("{{SITE_NAME}}", site_name))
    if faq_jsonld:
        head_filled += "\n" + faq_jsonld

    # Вкладываем контент в layout
    html = (layout
            .replace("{{ site.name }}", site_name)
            .replace("{{ content }}", head_filled + "\n" + content))
    return html
