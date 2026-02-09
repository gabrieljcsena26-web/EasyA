# check_backend.py
# Script de check-up completo do backend
# Cria tabelas, insere dados de teste e verifica relacionamentos

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, SQLALCHEMY_DATABASE_URL
from app.models import models

# Conexão com o mesmo banco do projeto
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# -----------------------
# Criar tabelas
# -----------------------
Base.metadata.create_all(bind=engine)
print("✅ Tabelas criadas com sucesso (ou já existiam)")

# -----------------------
# Inserção de dados teste
# -----------------------
try:
    # Estabelecimento
    est = models.Estabelecimento(nome="Clinica Central", telefone="11111111", slug="clinica-central")
    session.add(est)
    session.commit()
    print(f"✅ Estabelecimento criado com ID: {est.id}")

    # Funcionários
    f1 = models.Funcionario(nome="Dr. Silva", telefone="22222222", estabelecimento_id=est.id)
    f2 = models.Funcionario(nome="Dra. Costa", telefone="33333333", estabelecimento_id=est.id)
    session.add_all([f1, f2])
    session.commit()
    print(f"✅ Funcionários criados com IDs: {f1.id}, {f2.id}")

    # Clientes
    c1 = models.Cliente(nome="João", telefone="44444444", observacoes="Primeira consulta", tipo_servico="Consulta", estabelecimento_id=est.id)
    c2 = models.Cliente(nome="Maria", telefone="55555555", observacoes="Retorno", tipo_servico="Consulta", estabelecimento_id=est.id)
    session.add_all([c1, c2])
    session.commit()
    print(f"✅ Clientes criados com IDs: {c1.id}, {c2.id}")

    # Agendamentos
    a1 = models.Agendamento(cliente_id=c1.id, funcionario_id=f1.id, descricao="Consulta inicial")
    a2 = models.Agendamento(cliente_id=c2.id, funcionario_id=f2.id, descricao="Retorno de avaliação")
    session.add_all([a1, a2])
    session.commit()
    print(f"✅ Agendamentos criados com IDs: {a1.id}, {a2.id}")

except Exception as e:
    print("❌ Erro durante inserção de dados:", e)
    session.rollback()

# -----------------------
# Verificação das tabelas no banco
# -----------------------
with engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
    tables = [row[0] for row in result.fetchall()]
    print("\n🔹 Tabelas no banco:")
    for table in tables:
        print("  -", table)

    # Mostrar registros de cada tabela
    for table in tables:
        result = conn.execute(text(f"SELECT * FROM {table};"))
        rows = result.fetchall()
        print(f"\n🔹 Dados da tabela {table}:")
        if rows:
            for row in rows:
                print(" ", row)
        else:
            print("  (vazia)")

session.close()
print("\n✅ Check-up completo finalizado. Se todos os ✅ apareceram, seu backend está funcional!")
