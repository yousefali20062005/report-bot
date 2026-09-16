import json
import time

import httpx

GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

MODEL_FALLBACK_CHAIN = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


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
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _try_model(cfg, model: str, payload: dict, timeout: float) -> dict:
    url = GENERATE_URL.format(model=model)
    headers = {"x-goog-api-key": cfg.gemini_api_key}
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        return _extract_json(text)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("empty or malformed Gemini response") from exc


def generate_report(cfg, topic: str, pages: int, lang: str) -> dict:
    words = max(pages * 250, 400)
    payload = {
        "contents": [{"parts": [{"text": build_prompt(topic, pages, lang)}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": min(words * 2 + 2000, 60000),
        },
    }
    models = []
    if cfg.gemini_model:
        models.append(cfg.gemini_model)
    for m in MODEL_FALLBACK_CHAIN:
        if m not in models:
            models.append(m)

    errors = []
    for model in models:
        for attempt in range(2):
            try:
                return _try_model(cfg, model, payload, 240)
            except Exception as exc:
                errors.append(f"{model}: {exc}")
                time.sleep(2)
    raise RuntimeError("All Gemini models failed: " + "; ".join(errors[-8:]))