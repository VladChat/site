import re, json

def extract_faq(article_text):
    faq_html, faq_entities = [], []
    faq_section = re.search(r"# FAQ(.*?)(# Sources|$)", article_text, re.S)
    if faq_section:
        faq_block = faq_section.group(1).strip()
        qa_pairs = re.findall(r"Q:\s*(.*?)\nA:\s*(.*?)(?=\nQ:|\Z)", faq_block, re.S)
        for q, a in qa_pairs:
            faq_html.append(f"<details><summary>{q.strip()}</summary><p>{a.strip()}</p></details>")
            faq_entities.append({
                "@type": "Question",
                "name": q.strip(),
                "acceptedAnswer": {"@type": "Answer", "text": a.strip()}
            })

    faq_block_html, faq_block_jsonld = "", ""
    if faq_html:
        faq_block_html = "<section class='article-card'><h3>FAQs</h3>\n" + "\n".join(faq_html) + "\n</section>"
    if faq_entities:
        faq_block_jsonld = '<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_entities
        }, ensure_ascii=False) + "</script>"
    return faq_block_html, faq_block_jsonld
