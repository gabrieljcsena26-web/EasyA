from app.db.database import SessionLocal
from app.models.models import Estabelecimento

def main():
    s = SessionLocal()
    e = s.query(Estabelecimento).first()
    if e:
        print(e.id, e.slug)
    else:
        print('NO_EST')

if __name__ == '__main__':
    main()
