from app.db import database
from sqlalchemy import text

engine = database.engine
with engine.connect() as conn:
    res = conn.execute(text("PRAGMA table_info('estabelecimentos')")).fetchall()
    cols = [r[1] for r in res]
    print('Columns:', cols)
    if 'lembrete_horas_antes' not in cols:
        print('Adding column lembrete_horas_antes')
        conn.execute(text("ALTER TABLE estabelecimentos ADD COLUMN lembrete_horas_antes JSON"))
        print('Column added')
    else:
        print('Column exists')
