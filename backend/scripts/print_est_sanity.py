"""Print a sanity summary for a business (estabelecimento) configuration.

Usage:
    cd Backend
    python -m scripts.print_est_sanity --list
    python -m scripts.print_est_sanity --slug barbeariaG

What it prints:
- Estabelecimento basic data (id, slug, hours, idioma_padrao)
- SetupProfile timezone + key scheduling policy snippets
- Confirmation policy (computed defaults) and the raw confirmation container
- Opening hours, holidays, breaks, grace minutes, per-professional overrides

This is intended as a quick checklist before enabling WhatsApp Cloud API templates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from app.core.locale import resolve_timezone, resolve_lang
from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile, Funcionario

from app.api.booking.routes import (
    _extract_confirmation_policy,
    _extract_open_days_and_holidays,
    _extract_opening_hours,
    _extract_break_window,
    _extract_break_window_for_prof,
    _extract_end_of_shift_grace_minutes,
)


def _fmt_time(t) -> str | None:
    if not t:
        return None
    try:
        return t.strftime("%H:%M")
    except Exception:
        return str(t)


def _pretty(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(obj)


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", help="Estabelecimento.slug")
    g.add_argument("--list", action="store_true", help="List available establishments (id/slug/nome)")
    ap.add_argument("--limit", type=int, default=50, help="When listing, max rows to print")
    ap.add_argument("--dump-payload", action="store_true", help="Dump full SetupProfile payload JSON")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.list:
            rows = (
                db.query(Estabelecimento)
                .order_by(Estabelecimento.id.asc())
                .limit(int(args.limit) if args.limit else 50)
                .all()
            )
            total = db.query(Estabelecimento).count()
            print(f"count: {total}")
            for e in rows:
                print(f"{e.id}\t{e.slug}\t{getattr(e, 'nome', None)}")
            return

        est = db.query(Estabelecimento).filter_by(slug=str(args.slug)).first()
        if not est:
            raise SystemExit(f"estabelecimento not found for slug={args.slug}")

        sp = db.query(SetupProfile).filter_by(estabelecimento_id=est.id).first()
        payload = sp.payload if sp and isinstance(sp.payload, dict) else {}

        tzinfo, tz_name = resolve_timezone(payload)

        print("== Estabelecimento ==")
        print("id:", est.id)
        print("slug:", est.slug)
        print("nome:", est.nome)
        print("idioma_padrao:", getattr(est, "idioma_padrao", None))
        print("horario_inicio/fim:", getattr(est, "horario_inicio", None), "-", getattr(est, "horario_fim", None))
        print("timezone:", tz_name)
        print("now_local:", datetime.now(tzinfo).isoformat() if tzinfo else datetime.now().isoformat())

        lang = resolve_lang(estabelecimento_lang=getattr(est, "idioma_padrao", None))
        print("resolved_lang:", lang)

        print("\n== SetupProfile ==")
        print("exists:", bool(sp))
        print("setup_profile_id:", getattr(sp, "id", None))
        print("updated_at:", getattr(sp, "updated_at", None))

        if args.dump_payload:
            print("\n== SetupProfile.payload (full) ==")
            print(_pretty(payload))

        print("\n== Business hours / holidays ==")
        open_days, holidays = _extract_open_days_and_holidays(payload)
        opening_hours = _extract_opening_hours(payload)
        print("openDays:", _pretty(open_days) if open_days else None)
        print("openingHours:", _pretty(opening_hours) if opening_hours else None)
        print("holidays_count:", len(holidays))
        if holidays:
            print("holidays_sample:", ", ".join(sorted(list(holidays))[:10]))

        print("\n== Breaks (lunch/pauses) ==")
        bs, be = _extract_break_window(payload)
        print("business_break:", _fmt_time(bs), "->", _fmt_time(be))

        print("\n== End-of-shift grace (buffers) ==")
        grace_default = _extract_end_of_shift_grace_minutes(payload)
        print("default_grace_minutes:", grace_default)

        print("\n== Per-professional overrides ==")
        profs = db.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).order_by(Funcionario.id.asc()).all()
        if not profs:
            print("(no professionals)")
        for p in profs[:20]:
            p_bs, p_be = _extract_break_window_for_prof(payload, p)
            p_grace = _extract_end_of_shift_grace_minutes(payload, prof=p)
            if p_bs or p_be or (p_grace != grace_default):
                print(f"- {p.id} {p.nome}:")
                if p_bs or p_be:
                    print("  break:", _fmt_time(p_bs), "->", _fmt_time(p_be))
                if p_grace != grace_default:
                    print("  grace_min:", p_grace)

        print("\n== Confirmation policy (computed) ==")
        computed = _extract_confirmation_policy(payload)
        print(_pretty(computed))

        # Show raw container (what admin/dashboard should be editing)
        raw_confirmation = None
        if isinstance(payload.get("confirmation"), dict):
            raw_confirmation = payload.get("confirmation")
        biz = payload.get("business") if isinstance(payload.get("business"), dict) else {}
        if raw_confirmation is None and isinstance(biz.get("confirmation"), dict):
            raw_confirmation = biz.get("confirmation")
        print("\nraw_confirmation_container:")
        print(_pretty(raw_confirmation) if raw_confirmation else None)

    finally:
        db.close()


if __name__ == "__main__":
    main()
