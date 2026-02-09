from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

payloads = [
    {"username": "admin", "password": "123"},
    {"username": "ana-beleza-madrid", "password": "123"},
]

for p in payloads:
    print("\nTrying login with:", p)
    resp = client.post("/auth/login", json=p)
    print("Status:", resp.status_code)
    print("Body:", resp.text)
    if resp.status_code >= 500:
        resp.raise_for_status()
