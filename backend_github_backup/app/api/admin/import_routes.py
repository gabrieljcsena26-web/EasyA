from __future__ import annotations

import csv
import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Body
from sqlalchemy.orm import Session

from app.core.locale import resolve_timezone
from app.core.trial import TRIAL_DAYS_DEFAULT, ensure_trial_started
from app.db.database import get_db
from app.models.models import Agendamento, Cliente, Estabelecimento, Funcionario, Service, SetupProfile
from app.services.scheduler import agendar_lembretes_para_agendamento

# Reuse existing admin auth + establishment resolution.
from app.api.admin.routes import check_superadmin, _get_primary_estabelecimento


router = APIRouter(prefix="/admin/import", tags=["admin-import"])


_PHONE_RE = re.compile(r"(\+\d[\d\s().-]{7,}\d)")


def _normalize_phone(v: str | None) -> str:
    if not v:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    s = s.replace("whatsapp:", "").replace("WhatsApp:", "").strip()
    has_plus = s.startswith("+")
    digits = re.sub(r"\D+", "", s)
    if not digits:
        return ""
    return ("+" if has_plus else "+") + digits


def _extract_phone(*parts: str) -> str:
    blob = "\n".join([str(p or "") for p in parts if p is not None])
    m = _PHONE_RE.search(blob)
    if not m:
        return ""
    return _normalize_phone(m.group(1))


def _dt_to_local_naive(dt: Any, tz) -> datetime | None:
    if dt is None:
        return None

    # icalendar returns datetime/date types (sometimes vDDDTypes)
    value = getattr(dt, "dt", dt)

    # All-day events: date
    try:
        from datetime import date as dt_date

        if isinstance(value, dt_date) and not isinstance(value, datetime):
            return None
    except Exception:
        pass

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        aware = value.replace(tzinfo=tz)
    else:
        aware = value

    try:
        local = aware.astimezone(tz)
    except Exception:
        local = aware

    return local.replace(tzinfo=None)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _trial_raise_expired(end_utc: datetime | None) -> None:
    raise HTTPException(
        status_code=402,
        detail={
            "code": "TRIAL_EXPIRED",
            "message": "Trial expired. Choose a plan to continue.",
            "trial_end_utc": end_utc.isoformat() if end_utc else None,
        },
    )


def _is_private_host(hostname: str) -> bool:
    h = str(hostname or "").strip().lower()
    if not h:
        return True
    if h in ("localhost", "localhost.localdomain"):
        return True
    if h.endswith(".local"):
        return True
    return False


def _is_private_ip(ip_s: str) -> bool:
    try:
        ip = ipaddress.ip_address(str(ip_s))
    except Exception:
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_safe_fetch_url(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        raise HTTPException(status_code=400, detail="URL ausente")

    parsed = urlparse(u)
    if parsed.scheme not in ("https",):
        raise HTTPException(status_code=400, detail="Por segurança, aceitamos apenas URLs https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL inválida (sem hostname)")
    if _is_private_host(parsed.hostname):
        raise HTTPException(status_code=400, detail="URL não permitida")

    # Block direct IPs and resolved private IPs (basic SSRF mitigation)
    host = parsed.hostname
    try:
        # If host is already an IP literal
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", host) or ":" in host:
            if _is_private_ip(host):
                raise HTTPException(status_code=400, detail="URL não permitida")
        else:
            ip = socket.gethostbyname(host)
            if _is_private_ip(ip):
                raise HTTPException(status_code=400, detail="URL não permitida")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Falha ao resolver hostname")

    return u


def _parse_ics_bytes(raw: bytes) -> Any:
    try:
        from icalendar import Calendar

        return Calendar.from_ical(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Arquivo .ics inválido: {type(e).__name__}")


def _ics_preview_from_calendar(
    *,
    cal: Any,
    tz,
    tz_name: str,
    prof: Funcionario,
    svc: Service | None,
    db: Session,
):
    items = []
    starts = []
    ends = []

    for component in cal.walk():
        try:
            if str(getattr(component, "name", "")).upper() != "VEVENT":
                continue
        except Exception:
            continue

        uid = str(component.get("UID") or "").strip() or None
        summary = str(component.get("SUMMARY") or "").strip()
        description = str(component.get("DESCRIPTION") or "").strip()
        location = str(component.get("LOCATION") or "").strip()

        dtstart_raw = component.get("DTSTART")
        dtend_raw = component.get("DTEND")

        start_local = _dt_to_local_naive(dtstart_raw, tz)
        end_local = _dt_to_local_naive(dtend_raw, tz)

        if start_local is None:
            items.append(
                {
                    "uid": uid,
                    "summary": summary,
                    "description": description,
                    "start_local": None,
                    "end_local": None,
                    "duration_min": None,
                    "customer_name": None,
                    "customer_whatsapp": None,
                    "status": "skipped_all_day",
                    "conflict": False,
                }
            )
            continue

        if end_local is None or end_local <= start_local:
            end_local = start_local + timedelta(minutes=int(getattr(svc, "duration_min", 60) or 60))

        duration_min = int(max(1, (end_local - start_local).total_seconds() // 60))
        phone = _extract_phone(summary, description, location)

        name_guess = None
        if summary:
            name_guess = summary.strip()
        if description:
            m = re.search(r"(?im)^\s*(?:nome|cliente)\s*[:=-]\s*(.+?)\s*$", description)
            if m:
                name_guess = m.group(1).strip()

        status = "ok" if phone else "needs_phone"
        starts.append(start_local)
        ends.append(end_local)

        items.append(
            {
                "uid": uid,
                "summary": summary,
                "description": description,
                "start_local": start_local.isoformat(),
                "end_local": end_local.isoformat(),
                "duration_min": duration_min,
                "customer_name": name_guess,
                "customer_whatsapp": phone or None,
                "status": status,
                "conflict": False,
            }
        )

    existing = []
    if starts and ends:
        min_dt = min(starts)
        max_dt = max(ends)
        existing = (
            db.query(Agendamento)
            .filter(
                Agendamento.funcionario_id == prof.id,
                Agendamento.data_hora >= (min_dt - timedelta(days=1)),
                Agendamento.data_hora <= (max_dt + timedelta(days=1)),
            )
            .all()
        )

    def existing_end(ag: Agendamento) -> datetime:
        try:
            dur = int(getattr(ag.service, "duration_min", 60) or 60)
            buf = int(getattr(ag.service, "buffer_min", 0) or 0)
        except Exception:
            dur = 60
            buf = 0
        return (ag.data_hora or datetime.now()) + timedelta(minutes=dur + buf)

    for it in items:
        if not it.get("start_local") or not it.get("end_local"):
            continue
        try:
            st = datetime.fromisoformat(it["start_local"])
            en = datetime.fromisoformat(it["end_local"])
        except Exception:
            continue
        it["conflict"] = any(
            (ag.data_hora and _overlaps(st, en, ag.data_hora, existing_end(ag))) for ag in (existing or [])
        )

    summary_counts = {
        "total": len(items),
        "ready": len([x for x in items if x.get("status") == "ok" and not x.get("conflict")]),
        "needs_phone": len([x for x in items if x.get("status") == "needs_phone"]),
        "conflicts": len([x for x in items if x.get("conflict")]),
        "skipped": len([x for x in items if x.get("status") == "skipped_all_day"]),
    }

    return {
        "ok": True,
        "timezone": tz_name,
        "professional_id": prof.id,
        "service_id": svc.id if svc else None,
        "counts": summary_counts,
        "items": items,
    }


@router.post("/ics/preview")
async def preview_ics_import(
    file: UploadFile = File(...),
    professional_id: int = Form(...),
    service_id: int | None = Form(None),
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Parse an .ics and return a normalized preview (no DB writes)."""

    if not file or not getattr(file, "filename", ""):
        raise HTTPException(status_code=400, detail="Arquivo .ics ausente")

    est = _get_primary_estabelecimento(db, auth=auth)

    prof = (
        db.query(Funcionario)
        .filter(Funcionario.id == int(professional_id))
        .first()
    )
    if not prof:
        raise HTTPException(status_code=400, detail="Profissional não encontrado")
    if prof.estabelecimento_id != est.id:
        raise HTTPException(status_code=400, detail="Profissional não pertence a este estabelecimento")

    svc = None
    if service_id is not None:
        svc = db.query(Service).filter(Service.id == int(service_id)).first()
        if not svc:
            raise HTTPException(status_code=400, detail="Serviço não encontrado")
        if svc.estabelecimento_id != est.id:
            raise HTTPException(status_code=400, detail="Serviço não pertence a este estabelecimento")

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row and isinstance(setup_row.payload, dict) else {}

    # Gate by trial: preview is allowed, commit is what matters.
    tz, tz_name = resolve_timezone(setup_payload)

    try:
        raw = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Falha ao ler arquivo")

    cal = _parse_ics_bytes(raw)
    return _ics_preview_from_calendar(cal=cal, tz=tz, tz_name=tz_name, prof=prof, svc=svc, db=db)


@router.post("/ics/preview-url")
def preview_ics_import_from_url(
    url: str = Body(..., embed=True),
    professional_id: int = Body(..., embed=True),
    service_id: int | None = Body(None, embed=True),
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Fetch an iCal URL (e.g., Google Calendar secret iCal URL) and return a preview."""

    safe_url = _validate_safe_fetch_url(url)
    est = _get_primary_estabelecimento(db, auth=auth)

    prof = db.query(Funcionario).filter(Funcionario.id == int(professional_id)).first()
    if not prof:
        raise HTTPException(status_code=400, detail="Profissional não encontrado")
    if prof.estabelecimento_id != est.id:
        raise HTTPException(status_code=400, detail="Profissional não pertence a este estabelecimento")

    svc = None
    if service_id is not None:
        svc = db.query(Service).filter(Service.id == int(service_id)).first()
        if not svc:
            raise HTTPException(status_code=400, detail="Serviço não encontrado")
        if svc.estabelecimento_id != est.id:
            raise HTTPException(status_code=400, detail="Serviço não pertence a este estabelecimento")

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row and isinstance(setup_row.payload, dict) else {}
    tz, tz_name = resolve_timezone(setup_payload)

    try:
        import requests

        r = requests.get(safe_url, timeout=12, stream=True)
        r.raise_for_status()
        chunks = []
        size = 0
        max_bytes = 2 * 1024 * 1024
        for ch in r.iter_content(chunk_size=64 * 1024):
            if not ch:
                continue
            size += len(ch)
            if size > max_bytes:
                raise HTTPException(status_code=400, detail="Arquivo iCal muito grande")
            chunks.append(ch)
        raw = b"".join(chunks)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao baixar iCal: {type(e).__name__}")

    cal = _parse_ics_bytes(raw)
    return _ics_preview_from_calendar(cal=cal, tz=tz, tz_name=tz_name, prof=prof, svc=svc, db=db)


def _decode_text_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _detect_delimiter(sample: str) -> str:
    # A lot of EU exports use ';'
    candidates = [";", ",", "\t"]
    best = ","
    best_count = -1
    head = sample.splitlines()[:5]
    joined = "\n".join(head)
    for d in candidates:
        c = joined.count(d)
        if c > best_count:
            best_count = c
            best = d
    return best


def _csv_key(row: dict, *names: str) -> str:
    keys = {str(k).strip().lower(): k for k in (row or {}).keys()}
    for n in names:
        k = keys.get(str(n).strip().lower())
        if k is not None:
            v = row.get(k)
            return str(v or "").strip()
    return ""


@router.post("/clients-csv/preview")
async def preview_clients_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Preview CSV client import (no writes)."""

    if not file or not getattr(file, "filename", ""):
        raise HTTPException(status_code=400, detail="Arquivo CSV ausente")

    try:
        raw = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Falha ao ler arquivo")

    text = _decode_text_bytes(raw)
    delim = _detect_delimiter(text)
    lines = text.splitlines()
    if not lines:
        raise HTTPException(status_code=400, detail="CSV vazio")

    reader = csv.DictReader(lines, delimiter=delim)
    rows = []
    seen_phones: set[str] = set()
    duplicates_in_file = 0
    for i, row in enumerate(reader):
        if i > 5000:
            break
        if not isinstance(row, dict):
            continue
        name = _csv_key(row, "nome", "name", "cliente", "customer_name")
        phone_raw = _csv_key(row, "telefone", "phone", "whatsapp", "celular", "mobile", "customer_whatsapp")
        lang = _csv_key(row, "idioma", "lang", "language")
        notes = _csv_key(row, "observacoes", "observações", "notes", "note")
        phone = _normalize_phone(phone_raw)

        if phone:
            if phone in seen_phones:
                duplicates_in_file += 1
            else:
                seen_phones.add(phone)

        status = "ok" if phone else "needs_phone"
        rows.append(
            {
                "name": name or None,
                "phone": phone or None,
                "lang": lang or None,
                "notes": notes or None,
                "status": status,
            }
        )

    counts = {
        "total": len(rows),
        "ready": len([x for x in rows if x.get("status") == "ok"]),
        "needs_phone": len([x for x in rows if x.get("status") == "needs_phone"]),
    }

    existing_matches = 0
    try:
        est = _get_primary_estabelecimento(db, auth=auth)
        if est and seen_phones:
            existing_matches = (
                db.query(Cliente)
                .filter(Cliente.estabelecimento_id == est.id, Cliente.telefone.in_(list(seen_phones)))
                .count()
            )
    except Exception:
        existing_matches = 0

    return {
        "ok": True,
        "delimiter": delim,
        "counts": counts,
        "duplicates_in_file": duplicates_in_file,
        "existing_matches": existing_matches,
        "items": rows,
    }


@router.post("/clients-csv/commit")
def commit_clients_csv(
    payload: dict,
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Upsert clients by phone for the establishment."""

    est = _get_primary_estabelecimento(db, auth=auth)
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items vazio")

    created = 0
    updated = 0
    skipped = 0

    for it in items:
        if not isinstance(it, dict):
            skipped += 1
            continue
        phone = _normalize_phone(it.get("phone") or it.get("telefone") or it.get("whatsapp"))
        if not phone:
            skipped += 1
            continue
        name = str(it.get("name") or it.get("nome") or "").strip() or "Cliente"
        lang = str(it.get("lang") or it.get("idioma") or "").strip() or None
        notes = str(it.get("notes") or it.get("observacoes") or it.get("observações") or "").strip() or None

        row = db.query(Cliente).filter(Cliente.estabelecimento_id == est.id, Cliente.telefone == phone).first()
        if not row:
            row = Cliente(
                estabelecimento_id=est.id,
                telefone=phone,
                nome=name,
                idioma=lang or getattr(est, "idioma_padrao", None) or None,
                observacoes=notes,
            )
            db.add(row)
            created += 1
        else:
            changed = False
            if name and name != row.nome:
                row.nome = name
                changed = True
            if lang and lang != getattr(row, "idioma", None):
                row.idioma = lang
                changed = True
            if notes and notes != getattr(row, "observacoes", None):
                row.observacoes = notes
                changed = True
            if changed:
                updated += 1

    db.commit()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped}


@router.post("/ics/commit")
def commit_ics_import(
    payload: dict,
    db: Session = Depends(get_db),
    auth=Depends(check_superadmin),
):
    """Commit a previously previewed import into Clientes + Agendamentos and schedule reminders."""

    est = _get_primary_estabelecimento(db, auth=auth)

    setup_row = db.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est.id).first()
    setup_payload = setup_row.payload if setup_row and isinstance(setup_row.payload, dict) else {}

    # Trial gating + start-on-first-use
    setup_payload_next, trial_status = ensure_trial_started(setup_payload, trial_days=TRIAL_DAYS_DEFAULT)
    if trial_status.expired:
        _trial_raise_expired(trial_status.end_utc)

    # Persist trial start/end if needed
    try:
        if setup_payload_next is not setup_payload:
            if setup_row:
                setup_row.payload = setup_payload_next
            else:
                setup_row = SetupProfile(estabelecimento_id=est.id, payload=setup_payload_next)
                db.add(setup_row)
            db.commit()
            setup_payload = setup_payload_next
    except Exception:
        setup_payload = setup_payload_next

    professional_id = payload.get("professional_id")
    if professional_id is None:
        raise HTTPException(status_code=400, detail="professional_id ausente")

    prof = db.query(Funcionario).filter(Funcionario.id == int(professional_id)).first()
    if not prof:
        raise HTTPException(status_code=400, detail="Profissional não encontrado")
    if prof.estabelecimento_id != est.id:
        raise HTTPException(status_code=400, detail="Profissional não pertence a este estabelecimento")

    service_id = payload.get("service_id")
    svc = None
    if service_id is not None:
        svc = db.query(Service).filter(Service.id == int(service_id)).first()
        if not svc:
            raise HTTPException(status_code=400, detail="Serviço não encontrado")
        if svc.estabelecimento_id != est.id:
            raise HTTPException(status_code=400, detail="Serviço não pertence a este estabelecimento")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="items vazio")

    tz, _tz_name = resolve_timezone(setup_payload)

    imported = 0
    skipped = 0
    duplicates = 0
    scheduled = 0

    for it in items:
        if not isinstance(it, dict):
            skipped += 1
            continue

        start_local_s = it.get("start_local")
        if not start_local_s:
            skipped += 1
            continue

        phone = _normalize_phone(it.get("customer_whatsapp"))
        name = str(it.get("customer_name") or "").strip() or "Cliente"
        summary = str(it.get("summary") or "").strip()

        if not phone:
            skipped += 1
            continue

        try:
            start_local = datetime.fromisoformat(str(start_local_s))
        except Exception:
            skipped += 1
            continue

        # Ensure we store naive local datetimes like the rest of the system.
        if start_local.tzinfo is not None:
            try:
                start_local = start_local.astimezone(tz).replace(tzinfo=None)
            except Exception:
                start_local = start_local.replace(tzinfo=None)

        # Find or create client by phone within this establishment
        cliente = (
            db.query(Cliente)
            .filter(Cliente.estabelecimento_id == est.id, Cliente.telefone == phone)
            .first()
        )
        if not cliente:
            cliente = Cliente(
                nome=name,
                telefone=phone,
                estabelecimento_id=est.id,
                idioma=getattr(est, "idioma_padrao", None) or None,
            )
            db.add(cliente)
            db.flush()

        # Dedupe: same professional + same start + same phone
        existing = (
            db.query(Agendamento)
            .join(Cliente, Cliente.id == Agendamento.cliente_id)
            .filter(
                Agendamento.funcionario_id == prof.id,
                Agendamento.data_hora == start_local,
                Cliente.telefone == phone,
                Cliente.estabelecimento_id == est.id,
            )
            .first()
        )
        if existing:
            duplicates += 1
            continue

        ag = Agendamento(
            cliente_id=cliente.id,
            funcionario_id=prof.id,
            service_id=svc.id if svc else None,
            descricao=summary or "Importado da agenda",
            data_hora=start_local,
            status="confirmado",
        )
        db.add(ag)
        db.flush()
        imported += 1

        # Schedule reminders/confirmations for future appointments.
        try:
            agendar_lembretes_para_agendamento(
                ag,
                cliente,
                lang=getattr(cliente, "idioma", None) or None,
                db=db,
                estabelecimento_id=est.id,
            )
            scheduled += 1
        except Exception:
            pass

    db.commit()

    return {
        "ok": True,
        "imported": imported,
        "scheduled": scheduled,
        "duplicates": duplicates,
        "skipped": skipped,
    }
