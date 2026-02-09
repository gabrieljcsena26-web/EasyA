from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.models.models import Agendamento, Notificacao

router = APIRouter(prefix="/sync", tags=["sync"])

def iso_to_dt(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except:
        return None

@router.get("/changes")
def get_changes(request: Request, since: Optional[str] = None, db: Session = Depends(get_db)):
    last = iso_to_dt(since)
    
    qn = db.query(Notificacao)
    qa = db.query(Agendamento)
    
    if last:
        qn = qn.filter(Notificacao.criado_em > last)
        qa = qa.filter(Agendamento.updated_at > last)
    
    nots = qn.order_by(Notificacao.criado_em.asc()).all()
    ags = qa.order_by(Agendamento.updated_at.asc()).all()
    
    if not nots and not ags:
        if request and request.headers.get("if-modified-since"):
            raise HTTPException(status_code=304)
        return {"notificacoes": [], "agendamentos": []}
    
    newest = None
    times = []
    if nots:
        times.append(max(n.criado_em for n in nots))
    if ags:
        times.append(max(a.updated_at for a in ags))
    if times:
        newest = max(times)
    
    return {
        "notificacoes": [n.to_dict() for n in nots],
        "agendamentos": [a.to_dict() for a in ags],
        "last_modified": newest.isoformat() if newest else None
    }
