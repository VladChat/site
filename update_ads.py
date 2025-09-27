# Optional: if you ever baked ad placeholders into old posts and want to replace them in-place.
import pathlib, re

ROOT = pathlib.Path(__file__).parent
for html in ROOT.glob("posts/**/*.html"):
    txt = html.read_text(encoding="utf-8")
    # Example: replace old placeholder with slot include
    txt2 = txt.replace("{{AD_CODE}}", '<div class="ad-slot" data-ad="slot2"></div>')
    if txt2 != txt:
        html.write_text(txt2, encoding="utf-8")
        print("Updated ads in", html)
