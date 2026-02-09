from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.models import Estabelecimento, SetupProfile

from main import app


def _auth_header_for_est(est: Estabelecimento) -> dict:
    token = create_access_token(
        {
            "username": est.slug,
            "slug": est.slug,
            "estabelecimento_id": est.id,
        },
        expires_in_minutes=30,
    )
    return {"Authorization": f"Bearer {token}"}


def _get_first_est() -> Estabelecimento:
    s = SessionLocal()
    try:
        est = s.query(Estabelecimento).first()
        assert est is not None
        return est
    finally:
        s.close()


def _get_setup_payload(est_id: int) -> dict:
    s = SessionLocal()
    try:
        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
        if not sp:
            return {}
        return sp.payload  # type: ignore[return-value]
    finally:
        s.close()


def _ensure_setup_profile(est_id: int) -> None:
    s = SessionLocal()
    try:
        sp = s.query(SetupProfile).filter(SetupProfile.estabelecimento_id == est_id).first()
        if not sp:
            sp = SetupProfile(estabelecimento_id=est_id, payload={})
            s.add(sp)
        elif not isinstance(sp.payload, dict):
            sp.payload = {}
            s.add(sp)
        s.commit()
    finally:
        s.close()


@dataclass
class _DummyStripeData:
    object: dict


@dataclass
class _DummyStripeEvent:
    type: str
    data: _DummyStripeData


def test_stripe_webhook_updates_setup_profile_and_activates_plan(monkeypatch):
    """Webhook should persist Stripe IDs/status and flip trial.active_plan when subscription becomes active."""

    client = TestClient(app)
    est = _get_first_est()
    headers = _auth_header_for_est(est)

    # In production, SetupProfile typically exists already (setup wizard). Make test deterministic.
    _ensure_setup_profile(est.id)

    # Patch webhook config + signature verification to avoid depending on real Stripe secrets in unit tests.
    import app.api.billing.routes as billing_routes

    monkeypatch.setattr(billing_routes, "is_stripe_webhook_configured", lambda: True)

    called = {"update": 0, "trial": 0}

    orig_update = billing_routes._update_billing_payload
    orig_trial = billing_routes._set_trial_active_plan

    def _wrap_update(*args, **kwargs):
        called["update"] += 1
        return orig_update(*args, **kwargs)

    def _wrap_trial(*args, **kwargs):
        called["trial"] += 1
        return orig_trial(*args, **kwargs)

    monkeypatch.setattr(billing_routes, "_update_billing_payload", _wrap_update)
    monkeypatch.setattr(billing_routes, "_set_trial_active_plan", _wrap_trial)

    # Simulate a subscription update webhook payload.
    subscription_id = "sub_test_123"
    customer_id = "cus_test_456"

    dummy_event = _DummyStripeEvent(
        type="customer.subscription.updated",
        data=_DummyStripeData(
            object={
                "id": subscription_id,
                "customer": customer_id,
                "status": "active",
                "current_period_end": 1893456000,
                "metadata": {"estabelecimento_id": str(est.id)},
            }
        ),
    )

    monkeypatch.setattr(billing_routes, "verify_and_construct_webhook_event", lambda payload, sig_header: dummy_event)

    r = client.post(
        "/billing/stripe/webhook",
        content=b"{}",
        headers={"stripe-signature": "test", **headers},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True

    assert called["update"] >= 1
    assert called["trial"] >= 1

    payload = _get_setup_payload(est.id)
    assert isinstance(payload, dict)
    billing = payload.get("billing") if isinstance(payload.get("billing"), dict) else {}
    stripe_obj = billing.get("stripe") if isinstance(billing.get("stripe"), dict) else {}
    trial = payload.get("trial") if isinstance(payload.get("trial"), dict) else {}

    assert stripe_obj.get("customer_id") == customer_id
    assert stripe_obj.get("subscription_id") == subscription_id
    assert stripe_obj.get("subscription_status") == "active"
    assert trial.get("active_plan") is True


def test_subscription_status_endpoint_reflects_payload(monkeypatch):
    client = TestClient(app)
    est = _get_first_est()
    headers = _auth_header_for_est(est)

    # Make the endpoint deterministic in tests.
    import app.api.billing.routes as billing_routes

    monkeypatch.setattr(billing_routes, "is_stripe_configured", lambda: True)
    monkeypatch.setattr(billing_routes, "is_stripe_subscription_configured", lambda: True)
    monkeypatch.setattr(billing_routes, "is_stripe_webhook_configured", lambda: True)

    r = client.get("/billing/subscription/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True

    data = body.get("data") or {}
    stripe = (data.get("stripe") or {})
    trial = (data.get("trial") or {})

    assert stripe.get("configured") is True
    assert stripe.get("subscription_configured") is True
    assert stripe.get("webhook_configured") is True
    assert isinstance(trial.get("active_plan"), bool)
