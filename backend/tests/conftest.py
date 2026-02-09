import pytest

from app.db.database import SessionLocal
from app.models.models import Estabelecimento, Service, Funcionario

from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="session", autouse=True)
def ensure_demo_data():
    """Ensure a deterministic establishment + service + professional exist for tests.

    This runs once per test session and will create minimal demo data if missing.
    """
    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        if not est:
            est = Estabelecimento(nome="Demo Est", telefone="+000000000", slug="demo-est", email="demo@example.com")
            s.add(est)
            s.flush()

        svc = s.query(Service).filter(Service.estabelecimento_id == est.id).first()
        if not svc:
            svc = Service(estabelecimento_id=est.id, name="Demo Service", duration_min=60, buffer_min=0, price_cents=1000)
            s.add(svc)
            s.flush()

        prof = s.query(Funcionario).filter(Funcionario.estabelecimento_id == est.id).first()
        if not prof:
            prof = Funcionario(nome="Demo Prof", telefone="+111111111", estabelecimento_id=est.id)
            s.add(prof)
            s.flush()

        s.commit()
    finally:
        s.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)
