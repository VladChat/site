# =========================
# File: generate.py
# =========================
import argparse
import json
import os
import re
from pathlib import Path

from writer.config import load_configs
from writer.prompts import build_prompt
from writer.llm import call_openai
from writer.faq import extract_faq
from writer.render import render_post_html
from writer.storage import save_post, fetch_news_from_rss


def _persist_keyword_index(configs, next_idx: int) -> None:
    """Сохраняем keyword_index без потери остальных полей state.json."""
    root = Path(configs.get("root") or ".").resolve()
    state_path = Path(configs.get("state_path") or (root / "data" / "state.json"))
    try:
        state = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8")) or {}
            except Exception:
                state = {}
        state["keyword_index"] = int(next_idx)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Failed to persist keyword_index to state.json: {e}")


def _normalize_keywords(raw) -> list[str]:
    """
    Приводит keywords к списку строк.
    Поддерживаем:
      - список: ["a", "b"]
      - словарь: {"keywords":[...]} | {"items":[...]} | {"list":[...]} | {"data":[...]} | {"titles":[...]}
      - строку с разделителями (переводы строк, запятые, точки с запятой)
    """
    kws: list[str] = []

    if isinstance(raw, list):
        kws = [str(x).strip() for x in raw if str(x).strip()]
        return kws

    if isinstance(raw, dict):
        for k in ("keywords", "items", "list", "data", "titles"):
            v = raw.get(k)
            if isinstance(v, list):
                kws = [str(x).strip() for x in v if str(x).strip()]
                if kws:
                    return kws
        # если словарь без ожидаемых ключей — попробуем взять строковые значения
        flat = [str(v).strip() for v in raw.values() if isinstance(v, (str, int, float))]
        return [s for s in flat if s]

    if isinstance(raw, str):
        parts = re.split(r"[\r\n,;]+", raw)
        return [p.strip() for p in parts if p.strip()]

    return []


def _choose_keyword(configs, args) -> tuple[str, int | None]:
    """
    Возвращает (keyword, next_index_or_None).
    Если keywords.json отсутствует/пустой, уходим в RSS-фолбэк.
    """
    if args.keyword:
        return args.keyword, None

    root = Path(configs.get("root") or ".").resolve()
    kw_file = root / "config" / "keywords.json"

    kws: list[str] = []
    if kw_file.exists():
        try:
            raw = json.loads(kw_file.read_text(encoding="utf-8"))
        except Exception:
            # позволим хранить просто текстовый файл со списком слов по строкам
            raw = kw_file.read_text(encoding="utf-8")
        kws = _normalize_keywords(raw)

    if not kws:
        # Фолбэк: берём из RSS название как keyword
        feeds = configs.get("feeds") or []
        title, _ = fetch_news_from_rss(feeds)
        return title, None

    # циклический перебор индекса
    root = Path(configs.get("root") or ".").resolve()
    state_path = Path(configs.get("state_path") or (root / "data" / "state.json"))
    idx = -1
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8")) or {}
            raw_idx = st.get("keyword_index", -1)
            idx = int(raw_idx) if isinstance(raw_idx, (int, str)) and str(raw_idx).strip().lstrip("-").isdigit() else -1
        except Exception:
            idx = -1

    total = len(kws)
    next_idx = (idx + 1) % total
    return kws[next_idx], next_idx


def generate_post(keyword: str, summaries: str, configs) -> str:
    sys_prompt, usr_prompt = build_prompt(keyword, summaries, configs)
    article_md = call_openai(usr_prompt, sys_prompt)
    faq_html, faq_jsonld = extract_faq(article_md)
    html = render_post_html(keyword, article_md, faq_html, faq_jsonld, configs)
    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", help="Force keyword", default=None)
    parser.add_argument("--summaries", help="News summaries line", default=None)
    args = parser.parse_args()

    configs = load_configs()

    # Выбор ключевого слова и кратких «сигналов»
    keyword, chosen_idx = _choose_keyword(configs, args)
    if not args.summaries:
        # Из RSS
        _, summaries = fetch_news_from_rss(configs.get("feeds") or [])
    else:
        summaries = args.summaries

    # Генерация → Сохранение
    html = generate_post(keyword, summaries, configs)
    save_post(keyword, html, configs)

    # Обновляем индекс ключевого слова (последним шагом)
    if chosen_idx is not None:
        _persist_keyword_index(configs, chosen_idx)


if __name__ == "__main__":
    main()
