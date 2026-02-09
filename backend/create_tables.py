# create_tables.py
from app.db.database import Base, engine
# IMPORTAR TODOS OS MODELS para garantir que o SQLAlchemy conheça todas as tabelas
from app.models import models

# Cria todas as tabelas definidas nos models
Base.metadata.create_all(bind=engine)

print("All tables created successfully!")
