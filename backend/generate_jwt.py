# backend/generate_jwt.py

import jwt
from datetime import datetime, timedelta, timezone

# ⚠️ Essa chave precisa ser a mesma usada no seu backend em verify_access_token
SECRET_KEY = "SUA_CHAVE_SECRETA_AQUI"
ALGORITHM = "HS256"

def create_jwt(slug: str, expire_minutes: int = 60):
    """
    Gera um JWT para o cliente com slug fornecido.
    """
    payload = {
        "slug": slug,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

if __name__ == "__main__":
    slug_cliente = "clinica123"  # o slug do cliente que está no config.json
    token = create_jwt(slug_cliente)
    print("Token JWT gerado:")
    print(token)
