import argparse
from writer.config import load_configs
from writer.prompts import build_prompt
from writer.llm import call_openai          # <-- реальный вызов OpenAI
from writer.faq import extract_faq
from writer.render import render_post_html
from writer.storage import save_post, fetch_news_from_rss

def generate_post(keyword, summaries, configs):
    # 1) собираем промпт
    sys_prompt, usr_prompt = build_prompt(keyword, summaries, configs)
    # 2) зовём модель (writer.llm)
    text = call_openai(usr_prompt, sys_prompt)
    # 3) вытаскиваем FAQ (HTML + JSON-LD)
    faq_html, faq_jsonld = extract_faq(text)
    # 4) рендерим пост через шаблоны
    html = render_post_html(keyword, text, faq_html, faq_jsonld, configs)
    return html

if __name__ == "__main__":
    configs = load_configs()

    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Auto mode for GitHub Actions")
    parser.add_argument("--keyword", type=str, default=None)
    parser.add_argument("--summaries", type=str, default=None)
    args = parser.parse_args()

    if args.auto:
        keyword, summaries = fetch_news_from_rss(configs)
    else:
        keyword = args.keyword or "demo keyword"
        summaries = args.summaries or "Headline — Source"

    result = generate_post(keyword, summaries, configs)
    # save_post сохраняет В КОРЕНЬ posts/YYYY/MM/DD/slug.html (не site/)
    save_post(keyword, result, configs)
