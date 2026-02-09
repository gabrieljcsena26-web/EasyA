"""Seed de dados demo para EasyAgenda.

Cria:
- 1 estabelecimento (Ana Beleza · Madrid)
- 3 profissionais
- 3 serviços

Pode ser executado com:
    cd Backend
    python -m scripts.seed_demo_data

O script garante que as tabelas existam (Base.metadata.create_all)
antes de inserir os dados.
"""

from app.db.database import SessionLocal, Base, engine
from app.models import models as _models  # garante registro dos modelos
from app.models.models import Estabelecimento, Funcionario, Service


def main() -> None:
    # Garante que todas as tabelas existam (incluindo services)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1) Estabelecimento
        est = db.query(Estabelecimento).filter_by(slug="ana-beleza-madrid").first()
        if not est:
            est = Estabelecimento(
                nome="Ana Beleza · Madrid",
                telefone="+34 600 000 000",
                email="ana@example.com",
                slug="ana-beleza-madrid",
                idioma_padrao="pt-BR",
            )
            db.add(est)
            db.flush()
            print("[seed] Estabelecimento criado: Ana Beleza · Madrid")
        else:
            print("[seed] Estabelecimento já existia: Ana Beleza · Madrid")

        # 2) Profissionais
        profissionais = [
            ("Ana", "+34 600 000 001"),
            ("Júlia", "+34 600 000 002"),
            ("Pedro", "+34 600 000 003"),
        ]
        for nome, tel in profissionais:
            prof = (
                db.query(Funcionario)
                .filter_by(nome=nome, estabelecimento_id=est.id)
                .first()
            )
            if not prof:
                prof = Funcionario(
                    nome=nome,
                    telefone=tel,
                    estabelecimento_id=est.id,
                )
                db.add(prof)
                print(f"[seed] Profissional criado: {nome}")
            else:
                print(f"[seed] Profissional já existia: {nome}")

        # 3) Serviços
        servicos = [
            {
                "name": "Corte feminino",
                "duration_min": 60,
                "buffer_min": 15,
                "price_cents": 4500,
                "display_interval_min": 30,
            },
            {
                "name": "Coloração",
                "duration_min": 90,
                "buffer_min": 15,
                "price_cents": 7500,
                "display_interval_min": 30,
            },
            {
                "name": "Manicure",
                "duration_min": 45,
                "buffer_min": 15,
                "price_cents": 3000,
                "display_interval_min": 30,
            },
        ]
        for s in servicos:
            exists = (
                db.query(Service)
                .filter_by(name=s["name"], estabelecimento_id=est.id)
                .first()
            )
            if not exists:
                service = Service(
                    estabelecimento_id=est.id,
                    name=s["name"],
                    duration_min=s["duration_min"],
                    buffer_min=s["buffer_min"],
                    price_cents=s["price_cents"],
                    display_interval_min=s["display_interval_min"],
                )
                db.add(service)
                print(f"[seed] Serviço criado: {s['name']}")
            else:
                print(f"[seed] Serviço já existia: {s['name']}")

        db.commit()
        print("[seed] Concluído com sucesso.")
    except Exception as e:
        db.rollback()
        print(f"[seed] ERRO: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
