"""Seed a local establishment for dashboard/admin testing.

Usage:
  cd Backend
  python -m scripts.seed_barbeariag
  python -m scripts.seed_barbeariag --slug barbeariag --timezone America/Sao_Paulo --lang pt-BR

Creates/updates:
- Estabelecimento (basic fields)
- SetupProfile.payload.business.timezone
- SetupProfile.payload.confirmation (fixed14 recommended defaults)
- 1 service, 1 professional, 2 clients

Also prints a dev JWT token for the slug.
"""

from __future__ import annotations

import argparse
from copy import deepcopy

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.models import Cliente, Estabelecimento, Funcionario, Service, SetupProfile


def _ensure_dict(v):
    return v if isinstance(v, dict) else {}


def seed(*, slug: str, timezone: str, lang: str) -> dict:
    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
        if not est:
            est = Estabelecimento(
                nome="Barbearia G",
                telefone="5511999999999",
                email=f"{slug}@example.local",
                slug=slug,
                idioma_padrao=lang,
                horario_inicio=9,
                horario_fim=19,
            )
            db.add(est)
            db.commit()
            db.refresh(est)
        else:
            changed = False
            if not est.nome:
                est.nome = "Barbearia G"
                changed = True
            if not est.telefone:
                est.telefone = "5511999999999"
                changed = True
            if not est.email:
                est.email = f"{slug}@example.local"
                changed = True
            # Keep idioma_padrao aligned with requested seed lang to avoid stale locale in local tests.
            try:
                if str(getattr(est, "idioma_padrao", "") or "").strip() != str(lang or "").strip():
                    est.idioma_padrao = lang
                    changed = True
            except Exception:
                pass
            if changed:
                db.add(est)
                db.commit()

        sp = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est.id, payload={})
            db.add(sp)
            db.commit()
            db.refresh(sp)

        payload = deepcopy(_ensure_dict(sp.payload))
        biz = payload.get("business") if isinstance(payload.get("business"), dict) else {}
        biz = dict(biz)
        biz["timezone"] = timezone
        payload["business"] = biz

        # Fixed14 recommended confirmation policy (root-level container)
        conf = payload.get("confirmation") if isinstance(payload.get("confirmation"), dict) else {}
        conf = dict(conf)
        conf.setdefault("minLeadHours", 4)
        conf.setdefault("immediateHorizonHours", 36)
        conf["immediateWindowHours"] = 3
        conf["sendTimePrevDay"] = "14:00"
        conf["capDeadlinePrevDay"] = "17:00"
        conf["simpleModeEnabled"] = True
        conf["availabilityCutoffsOnly"] = True
        conf.setdefault("cutoffsEnabled", True)
        conf.setdefault("morningEndTime", "12:00")
        conf.setdefault("afternoonEndTime", "17:00")
        conf.setdefault("morningCutoffPrevDay", "20:00")
        conf.setdefault("afternoonCutoffSameDay", "12:00")
        conf.setdefault("nightCutoffSameDay", "16:00")
        payload["confirmation"] = conf

        sp.payload = payload
        db.add(sp)
        db.commit()

        # Seed service
        svc = db.query(Service).filter(Service.estabelecimento_id == est.id).first()
        if not svc:
            svc = Service(estabelecimento_id=est.id, name="Corte", duration_min=30, buffer_min=10, price_cents=5000)
            db.add(svc)

        # Seed professional
        prof = db.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        if not prof:
            prof = Funcionario(nome="Gustavo", telefone="5511988887777", estabelecimento_id=est.id)
            db.add(prof)

        db.commit()

        # Seed clients
        c1 = (
            db.query(Cliente)
            .filter(Cliente.estabelecimento_id == est.id, Cliente.telefone == "5511900000001")
            .first()
        )
        if not c1:
            c1 = Cliente(nome="Cliente BR", telefone="5511900000001", idioma="pt-BR", estabelecimento_id=est.id)
            db.add(c1)

        c2 = (
            db.query(Cliente)
            .filter(Cliente.estabelecimento_id == est.id, Cliente.telefone == "5511900000002")
            .first()
        )
        if not c2:
            c2 = Cliente(nome="Cliente ES", telefone="5511900000002", idioma="es-ES", estabelecimento_id=est.id)
            db.add(c2)

        db.commit()
        db.refresh(est)

        token = create_access_token({"username": est.slug, "slug": est.slug, "estabelecimento_id": est.id})

        return {
            "estabelecimento": {"id": est.id, "slug": est.slug, "nome": est.nome},
            "setup_profile_id": sp.id,
            "timezone": timezone,
            "lang": lang,
            "token": token,
        }
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="barbeariag")
    ap.add_argument("--timezone", default="Europe/Madrid")
    ap.add_argument("--lang", default="es-ES")
    args = ap.parse_args()

    result = seed(slug=str(args.slug), timezone=str(args.timezone), lang=str(args.lang))
    print("OK")
    print("estabelecimento_id:", result["estabelecimento"]["id"])
    print("slug:", result["estabelecimento"]["slug"])
    print("nome:", result["estabelecimento"]["nome"])
    print("setup_profile_id:", result["setup_profile_id"])
    print("timezone:", result["timezone"])
    print("lang:", result["lang"])
    print("dev_token:")
    print(result["token"])


if __name__ == "__main__":
    main()
