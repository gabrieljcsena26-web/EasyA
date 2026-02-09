from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def enqueue_pending_action(
    *,
    db,
    action_type: str,
    payload: dict,
    run_at: datetime,
    idempotency_key: Optional[str] = None,
) -> Optional[int]:
    """Enfileira uma PendingAction para execução futura.

    Usa idempotency_key (se fornecida) para evitar duplicatas.
    """

    from app.models.models import PendingAction

    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)
    else:
        run_at = run_at.astimezone(timezone.utc)

    if idempotency_key:
        existing = db.query(PendingAction).filter(PendingAction.idempotency_key == idempotency_key).first()
        if existing:
            # Atualiza o agendamento (ex: se mudou o horário do agendamento)
            existing.next_run_at = run_at
            existing.payload = payload
            db.add(existing)
            db.commit()
            return existing.id

    pa = PendingAction(
        action_type=action_type,
        payload=payload,
        status="pending",
        next_run_at=run_at,
        attempts=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
    )
    db.add(pa)
    db.commit()
    db.refresh(pa)
    return pa.id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def process_pending_actions(*, db=None, limit: int = 50) -> dict[str, Any]:
    """Processa PendingActions vencidas.

    Retorna contagem básica para logs/monitoramento.
    """

    from app.db.database import SessionLocal
    from app.models.models import PendingAction

    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True

    processed = 0
    succeeded = 0
    failed = 0

    try:
        now = _utcnow()
        actions = (
            db.query(PendingAction)
            .filter(
                PendingAction.status == "pending",
                PendingAction.next_run_at <= now,
            )
            .order_by(PendingAction.next_run_at.asc())
            .limit(limit)
            .all()
        )

        for a in actions:
            processed += 1
            try:
                ok = _dispatch_action(db=db, action=a)
                a.status = "done" if ok else "failed"
                if ok:
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                a.attempts = int(getattr(a, "attempts", 0) or 0) + 1
                if a.attempts >= int(getattr(a, "max_attempts", 3) or 3):
                    a.status = "failed"
                    failed += 1
                else:
                    # backoff simples
                    a.next_run_at = now
            db.add(a)

        if processed:
            db.commit()

        return {
            "ok": True,
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
        }
    finally:
        if owns_db and db is not None:
            db.close()


def _dispatch_action(*, db, action) -> bool:
    t = str(getattr(action, "action_type", "") or "").lower()
    payload = getattr(action, "payload", None)
    payload = payload if isinstance(payload, dict) else {}

    if t == "auto_cancel_no_response":
        return _auto_cancel_no_response(db=db, payload=payload)

    # Ação desconhecida: marca como concluída para não travar fila.
    return True


def _auto_cancel_no_response(*, db, payload: dict) -> bool:
    from app.models.models import Agendamento
    from app.services.notificar_interessados import notificar_interessados

    agendamento_id = payload.get("agendamento_id")
    if not agendamento_id:
        return True

    ag = db.query(Agendamento).filter(Agendamento.id == int(agendamento_id)).first()
    if not ag:
        return True

    # Só auto-cancelar se ainda não houve desfecho.
    status = str(getattr(ag, "status", "") or "")
    if status.lower().startswith("confirm"):
        return True
    if "cancel" in status.lower():
        return True

    ag.status = "cancelado_sem_resposta"
    db.add(ag)
    db.commit()

    try:
        notificar_interessados(ag, db)
    except Exception:
        pass

    return True
