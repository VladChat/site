# Vlad’s Blog — Automated AI-SEO Starter

**What it does**
- Generates posts with OpenAI (GPT), mixing your keywords with fresh RSS news.
- Renders responsive HTML with TOC, reading progress, related posts, and dynamic ads.
- Rebuilds index, RSS, sitemap, tags, and search index.
- Publishes to GitHub Pages on a schedule or on demand.

## Quick Start

1) **Upload files** to your repo (`VladChat/site`).  
2) In repo **Settings → Pages**, set:
   - Source: **GitHub Actions** (recommended), or **Deploy from a branch** (main).

3) Add secret **OPENAI_API_KEY** in **Settings → Secrets → Actions**.

4) Optionally edit `config.json`:
```json
{
  "cron": "0 12 * * *",
  "keywords": ["travel", "luggage"],
  "rss_feeds": ["https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"]
}
```

5) Run the workflow: **Actions → Automated AI-SEO Blog → Run workflow**.

## Local run
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python generate.py --auto
python rebuild_index.py
```

## Notes
- Ads are dynamic: edit `/ads/slot*.html` to change across all pages instantly.
- Design is responsive and accessible. Edit `/assets/style.css` to customize brand.
- Posts metadata are tracked in `data/state.json` for feeds and tags.
