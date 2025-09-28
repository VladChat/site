# =========================
# File: generate.py
# =========================
import argparse
import json
import os
from typing import Optional, Tuple

from writer.config import load_configs
from writer.prompts import build_prompt
from writer.llm import call_openai
from writer.faq import extract_faq
from writer.render import render_post_html
from writer.storage import save_post, fetch_news_from_rss


def _load_keywords_list(configs) -> Optional[list]:
    """Load keywords array from config/keywords.json. Returns list or None."""
    root = configs.get("root", ".")
    path = os.path.join(root, "config", "keywords.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Support either {"keywords": [...]} or a raw list [...]
        if isinstance(data, dict) and "keywords" in data and isinstance(data["keywords"], list):
            return [str(k).strip() for k in data["keywords"] if str(k).strip()]
        if isinstance(data, list):
            return [str(k).strip() for k in data if str(k).strip()]
    except FileNotFoundError:
        print(f"⚠️ keywords.json not found at {path}")
    except Exception as e:
        print(f"⚠️ Failed to load keywords.json: {e}")
    return None


def _choose_keyword(configs) -> Tuple[Optional[str], Optional[int]]:
    """
    Choose the next keyword (round-robin) and return (keyword, next_index).
    If keywords.json is missing, returns (None, None).
    """
    kws = _load_keywords_list(configs)
    if not kws:
        return None, None

    state_path = configs.get("state_path")
    # Default to -1 so first run picks index 0
    idx = -1
    try:
        if state_path and os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f) or {}
            idx = int(state.get("keyword_index", -1))
    except Exception as e:
        print(f"⚠️ Failed to read state.json for keyword_index: {e}")

    next_idx = (idx + 1) % len(kws)
    return kws[next_idx], next_idx


def _persist_keyword_index(configs, next_idx: int) -> None:
    """Persist the chosen keyword index into data/state.json (without losing other fields)."""
    state_path = configs.get("state_path")
    if not state_path:
        return
    try:
        state = {}
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                try:
                    state = json.load(f) or {}
                except Exception:
                    state = {}
        state["keyword_index"] = next_idx
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to persist keyword_index to state.json: {e}")


def generate_post(keyword: str, summaries: str, configs) -> str:
    """Build prompts, call LLM, extract FAQ, render HTML."""
    sys_prompt, usr_prompt = build_prompt(keyword, summaries, configs)
    article_md = call_openai(usr_prompt, sys_prompt)
    faq_html, faq_jsonld = extract_faq(article_md)
    html = render_post_html(keyword, article_md, faq_html, faq_jsonld, configs)
    return html


def main():
    configs = load_configs()

    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Auto mode for GitHub Actions")
    parser.add_argument("--keyword", type=str, default=None, help="Override keyword")
    parser.add_argument("--summaries", type=str, default=None, help="Override news summaries")
    args = parser.parse_args()

    # Always try to fetch fresh news signals from RSS
    rss_title, rss_summary = fetch_news_from_rss(configs)

    # Decide on the keyword
    chosen_keyword = args.keyword  # explicit override wins
    chosen_idx = None
    if not chosen_keyword:
        kw, idx = _choose_keyword(configs)  # from keywords.json (round-robin)
        chosen_keyword, chosen_idx = kw, idx
    if not chosen_keyword:
        # Fallback: use RSS title if no keywords.json and no override
        chosen_keyword = rss_title or "demo keyword"

    # Decide on the summaries (news context for the article)
    summaries = args.summaries or rss_summary or "Headline — Source"

    # Generate → Save → Persist keyword index (after save_post, to avoid overwrite)
    html = generate_post(chosen_keyword, summaries, configs)
    save_post(chosen_keyword, html, configs)
    if chosen_idx is not None:
        _persist_keyword_index(configs, chosen_idx)


if __name__ == "__main__":
    main()