import json
import time

import httpx

GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def build_prompt(topic: str, pages: int, lang: str) -> str:
    is_ar = lang == "ar"
    lang_line = "Arabic" if is_ar else "English"
    for_what = "أطروحة جامعية أكاديمية" if is_ar else "an academic university report"
    refs_line = "Arabic (author-year)" if is_ar else "English (APA style)"
    pages_words = max(pages * 250, 400)
    schema = (
        "Return ONLY valid JSON, no markdown fences, with exactly this structure:\n"
        '{"title": "...", "introduction": "...", '
        '"sections": [{"heading": "...", "content": "..."}, ...], '
        '"conclusion": "...", "references": ["...", "..."]}\n\n'
    )
    return (
        f"Write {for_what} about the topic: «{topic}». "
        f"Target length: about {pages_words} words (about {pages} pages). Language: {lang_line}.\n\n"
        + schema
        + f"Rules: academic tone, logical flow, 3-5 sections, references in {refs_line}."
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def generate_report(cfg, topic: str, pages: int, lang: str) -> dict:
    url = GENERATE_URL.format(model=cfg.gemini_model)
    payload = {
        "contents": [{"parts": [{"text": build_prompt(topic, pages, lang)}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": pages * 250 * 2 + 5000,
        },
    }
    headers = {"x-goog-api-key": cfg.gemini_api_key}
    for attempt in range(3):
        try:
            with httpx.Client(timeout=180) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            return _extract_json(text)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)