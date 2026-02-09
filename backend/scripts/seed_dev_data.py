import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models import models

def seed():
    db: Session = SessionLocal()
    try:
        slug = 'dev'
        est = db.query(models.Estabelecimento).filter(models.Estabelecimento.slug == slug).first()
        if not est:
            est = models.Estabelecimento(nome='Dev Estabelecimento', telefone='0000000000', email=f'{slug}@example.local', slug=slug)
            db.add(est)
            db.commit()
            db.refresh(est)

        svc = db.query(models.Service).filter(models.Service.estabelecimento_id == est.id).first()
        if not svc:
            svc = models.Service(estabelecimento_id=est.id, name='Corte', duration_min=30, price_cents=3000)
            db.add(svc)

        func = db.query(models.Funcionario).filter(models.Funcionario.estabelecimento_id == est.id).first()
        if not func:
            func = models.Funcionario(nome='João', telefone='000', estabelecimento_id=est.id)
            db.add(func)

        db.commit()

        clients = []
        for nome, tel in [('Cliente Um','111111111'), ('Cliente Dois','222222222')]:
            existing = db.query(models.Cliente).filter(models.Cliente.telefone == tel, models.Cliente.estabelecimento_id == est.id).first()
            if not existing:
                cl = models.Cliente(nome=nome, telefone=tel, estabelecimento_id=est.id)
                db.add(cl)
                db.commit()
                db.refresh(cl)
            else:
                cl = existing
            clients.append(cl)

        inv = db.query(models.Invoice).filter(models.Invoice.estabelecimento_id == est.id).first()
        if not inv and clients:
            inv = models.Invoice(estabelecimento_id=est.id, cliente_id=clients[0].id, descricao='Serviço teste', valor_centavos=3000, currency='BRL')
            db.add(inv)
            db.commit()

        print('seeded', {'estabelecimento_id': est.id, 'clients': [c.id for c in clients], 'invoice_id': inv.id if inv else None})
    finally:
        db.close()

if __name__ == '__main__':
    seed()
