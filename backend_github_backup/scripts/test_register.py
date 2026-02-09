from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

payload = {"nome": "Test Biz", "telefone": "111222333", "slug": "testbiz", "password": "123"}
print('Posting:', payload)
resp = client.post('/auth/register', json=payload)
print('Status:', resp.status_code)
print('Body:', resp.text)
# Raise if server error to show traceback when run normally
if resp.status_code >= 500:
    resp.raise_for_status()
