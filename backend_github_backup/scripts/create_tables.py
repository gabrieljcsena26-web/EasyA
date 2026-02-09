from app.db.database import engine
import app.models.models as models

models.Base.metadata.create_all(bind=engine)
print("Tables created successfully.")
