from app.db.database import SessionLocal
from app.models.models import Funcionario

def add(est_id=1, nome='Dev Prof', telefone='+1999999999'):
    s = SessionLocal()
    f = Funcionario(nome=nome, telefone=telefone, estabelecimento_id=est_id)
    s.add(f)
    s.commit()
    s.refresh(f)
    print('Created funcionario', f.id, f.nome, f.estabelecimento_id)
    s.close()

if __name__ == '__main__':
    add()
