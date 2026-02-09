import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.models import Estabelecimento

def generate(slug: str = 'dev'):
    db = SessionLocal()
    try:
        est = db.query(Estabelecimento).filter(Estabelecimento.slug == slug).first()
        if not est:
            # create minimal estabelecimento
            est = Estabelecimento(nome=f'Dev {slug}', telefone='0000000000', email=f'{slug}@example.local', slug=slug)
            db.add(est)
            db.commit()
            db.refresh(est)
        token = create_access_token({'username': est.slug, 'slug': est.slug, 'estabelecimento_id': est.id})
        print(token)
    finally:
        db.close()

if __name__ == '__main__':
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    generate(slug)
