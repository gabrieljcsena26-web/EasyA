from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

DEFAULT_TZ_NAME = os.getenv("EASYAGENDA_DEFAULT_TZ", "Europe/Madrid")
DEFAULT_LANG = os.getenv("EASYAGENDA_DEFAULT_LANG", "es-ES")
SUPPORTED_LANGS = {"pt-BR", "pt-PT", "en-US", "es-ES", "fr-FR", "ca-ES"}


def normalize_lang(lang: str | None) -> str:
    """Normalize incoming language tags to a supported message bundle."""
    s = (lang or "").strip()
    if not s:
        return DEFAULT_LANG

    # Accept-Language can be like: "en-US,en;q=0.9"
    if "," in s:
        s = s.split(",")[0].strip()

    s_low = s.lower().replace("_", "-")
    if s_low.startswith("pt-br"):
        return "pt-BR"
    if s_low.startswith("pt"):
        return "pt-PT"
    if s_low.startswith("en"):
        return "en-US"
    if s_low.startswith("es"):
        return "es-ES"
    if s_low.startswith("fr"):
        return "fr-FR"
    if s_low.startswith("ca"):
        return "ca-ES"

    # If already supported, keep it.
    if s in SUPPORTED_LANGS:
        return s

    return DEFAULT_LANG


def resolve_lang(*, cliente_lang: str | None = None, estabelecimento_lang: str | None = None, accept_language: str | None = None) -> str:
    """Resolve the best language for customer-facing messages."""
    for candidate in [cliente_lang, estabelecimento_lang, accept_language, DEFAULT_LANG]:
        normalized = normalize_lang(candidate)
        if normalized:
            return normalized
    return DEFAULT_LANG


def resolve_timezone(setup_payload: dict | None) -> tuple[object, str]:
    """Return (tzinfo, tz_name) based on SetupProfile payload.

    If zoneinfo is unavailable, returns UTC tzinfo.
    """
    payload = setup_payload if isinstance(setup_payload, dict) else {}
    business = payload.get("business") if isinstance(payload.get("business"), dict) else {}

    tz_name = str(business.get("timezone") or payload.get("timezone") or DEFAULT_TZ_NAME)

    if ZoneInfo is None:
        return timezone.utc, tz_name

    try:
        return ZoneInfo(tz_name), tz_name
    except Exception:
        return ZoneInfo(DEFAULT_TZ_NAME), DEFAULT_TZ_NAME


def as_utc(dt: datetime) -> datetime:
    if not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
