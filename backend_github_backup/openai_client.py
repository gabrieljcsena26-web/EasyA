# Backend/openai_client.py

import os
from dotenv import load_dotenv
from openai import OpenAI

# Carrega variáveis do .env (incluindo OPENAI_API_KEY)
load_dotenv()

def get_openai_client() -> OpenAI:
    """
    Retorna um cliente OpenAI já configurado com a API key do .env.
    Se a chave não for encontrada, levanta erro.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não encontrada no .env")
    return OpenAI(api_key=api_key)
