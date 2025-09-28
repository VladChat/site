import os
import json
import re
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from slugify import slugify as _slugify


def _slugify(text: str) -> str:
    s = (text or "").strip()
    s = _slugify(s, lowercase=True) if s else "post"
    return re.sub(r"-{2,}", "-", s).strip("-") or "post"


def _read_state(state_path: Path) -> dict:
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8")) or {}
        except Exception:
            # Никогда не падаем и не теряем историю
            return {}
    return {}


def _write_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = state or {}
    # Гарантируем ожидаемую структуру
    if "posts" not in state or not isinstance(state["posts"], list):
        state["posts"] = []
    if "seen_entries" not in state or not isinstance(state.get("seen_entries"), list):
        state["seen_entries"] = []
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _choose_content_root(repo_root: Path) -> Path:
    # Если есть blog-src/posts — используем его (текущая структура в архиве)
    blog_src_posts = repo_root / "blog-src" / "posts"
    if blog_src_posts.exists():
        return blog_src_posts
    # Иначе — классический каталог posts
    return repo_root / "posts"


def fetch_news_from_rss(rss_urls):
    """
    Упрощённая версия: возвращает (title, summary_line) самой свежей записи.
    Оставлено для совместимости со старым generate.py.
    """
    try:
        import feedparser
    except Exception:
        return "demo keyword", "Headline — Source"

    candidates = []
    for url in (rss_urls or []):
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title = getattr(entry, "title", "").strip() or "news"
                link = getattr(entry, "link", "").strip()
                ts = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                epoch = int(datetime(*ts[:6]).timestamp()) if ts else 0
                candidates.append((epoch, title, f"{title} — {link}" if link else title))
        except Exception:
            continue

    if not candidates:
        return "demo keyword", "Headline — Source"

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, title, line = candidates[0]
    return title, line


def save_post(title: str, html: str, configs: dict):
    """
    Сохраняет пост в blog-src/posts или posts (в зависимости от структуры),
    присваивает уникальное имя файла и добавляет запись в data/state.json,
    НЕ затирая старые посты.
    """
    repo_root = Path(configs.get("root") or ".").resolve()
    content_root = _choose_content_root(repo_root)

    now = datetime.now()
    y, m, d = f"{now.year:04d}", f"{now.month:02d}", f"{now.day:02d}"
    day_dir = content_root / y / m / d
    day_dir.mkdir(parents=True, exist_ok=True)

    base_slug = _slugify(title)
    unique = f"{base_slug}-{now.strftime('%Y%m%d-%H%M%S')}.html"
    file_path = day_dir / unique

    # Пишем HTML целиком
    file_path.write_text(html, encoding="utf-8")

    # Относительный URL всегда без base_url: он начинается с /posts/...
    url = f"/posts/{y}/{m}/{d}/{unique}"

    # Короткое описание из <article>
    try:
        soup = BeautifulSoup(html, "html.parser")
        article_text = (soup.find("article") or soup).get_text(" ", strip=True)
        desc = re.sub(r"\s+", " ", article_text)[:200]
    except Exception:
        desc = f"{title} article"

    # Обновляем state.json (только слоем слияния)
    state_path = Path(configs.get("state_path") or (repo_root / "data" / "state.json"))
    state = _read_state(state_path)
    posts = list(state.get("posts") or [])
    # Дедуп по URL
    posts = [p for p in posts if str(p.get("url")) != url]
    # Вставляем свежую запись в начало
    posts.insert(0, {
        "title": title,
        "url": url,
        "date": now.strftime("%Y-%m-%d"),
        "description": desc,
        "tags": ["travel"]
    })
    state["posts"] = posts
    _write_state(state_path, state)

    print(f"✅ Saved: {file_path}  →  {url}")
    return str(file_path), url
