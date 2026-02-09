import os
import logging
from typing import Optional, Any

try:
    import stripe  # type: ignore
except ImportError:  # stripe may not be installed in some environments
    stripe = None

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_DEFAULT_CURRENCY = os.getenv("STRIPE_DEFAULT_CURRENCY", "eur")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_SUBSCRIPTION_PRICE_ID = os.getenv("STRIPE_SUBSCRIPTION_PRICE_ID")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")


def is_stripe_configured() -> bool:
    """Return True if Stripe is importable and a secret key is configured."""
    return stripe is not None and bool(STRIPE_SECRET_KEY)


def is_stripe_webhook_configured() -> bool:
    return is_stripe_configured() and bool(STRIPE_WEBHOOK_SECRET)


def is_stripe_subscription_configured() -> bool:
    return is_stripe_configured() and bool(STRIPE_SUBSCRIPTION_PRICE_ID)


if is_stripe_configured():
    try:
        stripe.api_key = STRIPE_SECRET_KEY  # type: ignore[attr-defined]
    except Exception:
        # If something goes wrong while configuring, treat as not configured
        logger.exception("Failed to configure Stripe API key")


def _base_urls_for_invoice(invoice_id: int) -> tuple[str, str]:
    base = (FRONTEND_BASE_URL or "").rstrip("/") or "http://localhost:3000"
    success_url = f"{base}/billing/success?invoice_id={invoice_id}"
    cancel_url = f"{base}/billing/cancel?invoice_id={invoice_id}"
    return success_url, cancel_url


def create_checkout_session_for_invoice(
    *,
    invoice_id: int,
    amount_cents: int,
    currency: Optional[str],
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Optional[dict]:
    """Create a Stripe Checkout Session for an invoice.

    Returns a dict with {"id", "status", "url"} or None if Stripe is not configured
    or an error occurs. Never raises for the caller to keep billing flow robust.
    """

    if not is_stripe_configured():
        return None

    if amount_cents <= 0:
        # Do not attempt to create sessions for zero/negative amounts
        return None

    try:
        success_url, cancel_url = _base_urls_for_invoice(invoice_id)
        used_currency = (currency or STRIPE_DEFAULT_CURRENCY or "eur").lower()

        session = stripe.checkout.Session.create(  # type: ignore[union-attr]
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": used_currency,
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": description or f"EasyAgenda invoice #{invoice_id}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={"invoice_id": str(invoice_id), **(metadata or {})},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return {
            "id": getattr(session, "id", None),
            "status": getattr(session, "status", None),
            "url": getattr(session, "url", None),
        }
    except Exception:
        logger.exception("Failed to create Stripe checkout session for invoice %s", invoice_id)
        return None


def _base_urls_for_subscription() -> tuple[str, str]:
    base = (FRONTEND_BASE_URL or "").rstrip("/") or "http://localhost:3000"
    success_url = f"{base}/finance?stripe=success"
    cancel_url = f"{base}/finance?stripe=cancel"
    return success_url, cancel_url


def create_checkout_session_for_subscription(
    *,
    estabelecimento_id: int,
    estabelecimento_slug: str,
    estabelecimento_name: str | None = None,
    customer_email: str | None = None,
    metadata: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """Create a Stripe Checkout Session for a SaaS subscription (mode=subscription)."""

    if not is_stripe_subscription_configured():
        return None

    try:
        success_url, cancel_url = _base_urls_for_subscription()

        md: dict[str, str] = {
            "estabelecimento_id": str(estabelecimento_id),
            "estabelecimento_slug": str(estabelecimento_slug or ""),
        }
        if metadata:
            md.update({str(k): str(v) for k, v in metadata.items() if v is not None})

        session = stripe.checkout.Session.create(  # type: ignore[union-attr]
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_SUBSCRIPTION_PRICE_ID, "quantity": 1}],
            allow_promotion_codes=True,
            customer_email=customer_email or None,
            client_reference_id=str(estabelecimento_id),
            metadata=md,
            subscription_data={
                "metadata": md,
                # Helpful in Stripe dashboard
                "description": (estabelecimento_name or estabelecimento_slug or "EasyAgenda").strip()[:200],
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return {
            "id": getattr(session, "id", None),
            "status": getattr(session, "status", None),
            "url": getattr(session, "url", None),
        }
    except Exception:
        logger.exception("Failed to create Stripe checkout session for subscription est=%s", estabelecimento_id)
        return None


def create_billing_portal_session(*, customer_id: str) -> Optional[dict[str, Any]]:
    if not is_stripe_configured():
        return None

    cust = str(customer_id or "").strip()
    if not cust:
        return None

    try:
        base = (FRONTEND_BASE_URL or "").rstrip("/") or "http://localhost:3000"
        return_url = f"{base}/finance"
        session = stripe.billing_portal.Session.create(  # type: ignore[union-attr]
            customer=cust,
            return_url=return_url,
        )
        return {"id": getattr(session, "id", None), "url": getattr(session, "url", None)}
    except Exception:
        logger.exception("Failed to create Stripe billing portal session")
        return None


def verify_and_construct_webhook_event(*, payload: bytes, sig_header: str | None) -> Any:
    if not is_stripe_webhook_configured():
        raise RuntimeError("Stripe webhook not configured")
    if not sig_header:
        raise ValueError("Missing stripe-signature")

    # stripe.Event is typed as Any at runtime.
    return stripe.Webhook.construct_event(  # type: ignore[union-attr]
        payload=payload,
        sig_header=sig_header,
        secret=str(STRIPE_WEBHOOK_SECRET),
    )
