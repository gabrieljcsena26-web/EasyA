from models import Base
from Backend.app.db.database import engine

Base.metadata.create_all(bind=engine)
print("Tabelas criadas com sucesso!")
