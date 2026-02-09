"""Script para inspecionar dados demo no banco atual.

Executar a partir da pasta Backend:
    python -m scripts.inspect_demo_data
"""

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Funcionario, Service, Agendamento


def main() -> None:
    db = SessionLocal()
    try:
        ests = db.query(Estabelecimento).all()
        print(f"Estabelecimentos: {len(ests)}")
        for e in ests:
            print(f"  - id={e.id}, nome={e.nome}, slug={e.slug}")
        funcs = db.query(Funcionario).all()
        print(f"Funcionarios: {len(funcs)}")
        for f in funcs:
            print(f"  - id={f.id}, nome={f.nome}, est_id={f.estabelecimento_id}")
        services = db.query(Service).all()
        print(f"Services: {len(services)}")
        for s in services:
            print(f"  - id={s.id}, name={s.name}, est_id={s.estabelecimento_id}")
        ags = db.query(Agendamento).all()
        print(f"Agendamentos: {len(ags)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
