from app.db import database
from sqlalchemy import text
engine = database.engine
with engine.connect() as conn:
    res = conn.execute(text("PRAGMA table_info('estabelecimentos')")).fetchall()
    cols = [r[1] for r in res]
    print('Columns before:', cols)
    if 'idioma_padrao' not in cols:
        print('Adding column idioma_padrao')
        conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN idioma_padrao TEXT"))
        print('Added idioma_padrao')
    res2 = conn.execute(text("PRAGMA table_info('estabelecimentos')")).fetchall()
    print('Columns after:', [r[1] for r in res2])
