from app.db.database import SessionLocal
from app.models.models import Funcionario

def main():
    s = SessionLocal()
    fs = s.query(Funcionario).all()
    for f in fs:
        print(f.id, getattr(f, 'nome', None), f.estabelecimento_id)
    s.close()

if __name__ == '__main__':
    main()
