# Backend/config_loader.py
from pathlib import Path
import json

# BASE_DIR = pasta raiz do projeto (onde ficam Backend e Clientes)
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENTES_DIR = BASE_DIR / "Clientes"


def load_client_config(slug: str) -> dict:
    """
    Lê o config.json de um cliente pelo slug (nome da pasta, ex: 'CorteSupremo').
    """
    client_dir = CLIENTES_DIR / slug
    config_path = client_dir / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config não encontrado para o cliente: {slug}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
