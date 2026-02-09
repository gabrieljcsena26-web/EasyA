import json
import os

I18N_PATH = os.path.join(os.path.dirname(__file__))

_cache = {}


def _normalize_lang(lang: str | None) -> str:
    """Normalize incoming language tags to the supported message files.

    We intentionally keep the supported set small to avoid runtime FileNotFoundError.
    """
    s = (lang or "").strip()
    if not s:
        return "pt-BR"

    # Accept-Language can come like: "en-US,en;q=0.9"
    if "," in s:
        s = s.split(",")[0].strip()

    s_low = s.lower().replace("_", "-")
    if s_low.startswith("pt"):
        return "pt-BR"
    if s_low.startswith("en"):
        return "en-US"
    if s_low.startswith("es"):
        return "es-ES"
    return "pt-BR"


def _load_messages(lang: str) -> dict:
    lang = _normalize_lang(lang)
    if lang in _cache:
        return _cache[lang]
    path = os.path.join(I18N_PATH, f"messages_{lang}.json")
    try:
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    except Exception:
        # Fallback hard to pt-BR (never crash the API due to missing locale file)
        if lang != "pt-BR":
            return _load_messages("pt-BR")
        _cache[lang] = {}
    return _cache[lang]

def get_message(key, lang="pt-BR", **kwargs):
    messages = _load_messages(lang)
    msg = messages.get(key, key)
    return msg.format(**kwargs) if kwargs else msg
