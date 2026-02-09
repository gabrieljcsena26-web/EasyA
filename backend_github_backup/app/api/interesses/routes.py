from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Interesse, Cliente, Funcionario
from app.schemas.schemas import InteresseCreate, InteresseOut

router = APIRouter(prefix="/interesses", tags=["interesses"])

@router.post("", response_model=InteresseOut)
def criar_interesse(interesse: InteresseCreate, db: Session = Depends(get_db)):
    novo = Interesse(**interesse.dict())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@router.get("", response_model=list)
def listar_interesses(cliente_id: int = None, funcionario_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Interesse)
    if cliente_id:
        query = query.filter(Interesse.cliente_id == cliente_id)
    if funcionario_id:
        query = query.filter(Interesse.funcionario_id == funcionario_id)
    return query.order_by(Interesse.criado_em.desc()).all()

@router.delete("/{interesse_id}")
def remover_interesse(interesse_id: int, db: Session = Depends(get_db)):
    interesse = db.query(Interesse).filter(Interesse.id == interesse_id).first()
    if not interesse:
        raise HTTPException(status_code=404, detail="Interesse não encontrado")
    db.delete(interesse)
    db.commit()
    return {"ok": True}
