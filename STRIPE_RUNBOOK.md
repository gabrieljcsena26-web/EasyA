# Stripe subscriptions runbook (EasyAgenda)

Date: 2026-02-08

Goal: enable card payments for the SaaS subscription, and automatically flip `trial.active_plan=true` via Stripe webhooks.

## What exists in this repo

Backend endpoints:
- `GET /billing/subscription/status` (admin auth)
- `POST /billing/subscription/checkout` (admin auth) → returns a Stripe Checkout Session URL (mode=`subscription`)
- `POST /billing/subscription/portal` (admin auth) → returns Stripe Billing Portal URL (requires stored `customer_id`)
- `POST /billing/stripe/webhook` (public) → validates signature and updates `SetupProfile.payload.billing.stripe` + `payload.trial.active_plan`

Frontend:
- Finance page shows a “Pay by card” CTA when Stripe is configured.

## 1) Create Product + Price in Stripe

In Stripe Dashboard (Test mode first):
1. Products → Add product (e.g., “EasyAgenda – Subscription”)
2. Pricing → Add recurring price (e.g., monthly)
3. Copy the **Price ID** (looks like `price_...`)

That Price ID becomes `STRIPE_SUBSCRIPTION_PRICE_ID`.

## 2) Set environment variables (server)

Backend required for subscription checkout:
- `STRIPE_SECRET_KEY=sk_...`
- `STRIPE_SUBSCRIPTION_PRICE_ID=price_...`

Required for webhook processing (auto activation):
- `STRIPE_WEBHOOK_SECRET=whsec_...`

Recommended:
- `STRIPE_DEFAULT_CURRENCY=eur`
- `FRONTEND_BASE_URL=https://app.<your-domain>` (used for Stripe success/cancel return URLs)

Template: [Backend/.env.production.example](Backend/.env.production.example)

If you deploy with `docker-compose.prod.yml`, set these variables in a local `.env` file on the VPS (same folder as the compose file) or in your process manager secrets store. Do not commit secrets and do not paste `sk_...` / `whsec_...` into chat.

## 3) Configure the webhook endpoint in Stripe

Webhook URL (production):
- `https://api.<your-domain>/billing/stripe/webhook`

Events to enable (minimum viable):
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

Optional (kept for debugging):
- `invoice.paid`
- `invoice.payment_failed`

After creating the webhook endpoint in Stripe, copy the signing secret `whsec_...` into `STRIPE_WEBHOOK_SECRET`.

## 4) Verification checklist (staging/prod)

A) Confirm backend sees Stripe config
1. Login to admin
2. Call `GET /billing/subscription/status`
3. Expect:
   - `data.stripe.configured=true`
   - `data.stripe.subscription_configured=true`
   - `data.stripe.webhook_configured=true`

B) Create a checkout session
1. From admin Finance, click “Pay by card”
2. Expect redirect to `checkout.stripe.com/...`

C) Confirm webhook flips plan
1. Complete checkout (test card in test mode)
2. Stripe sends subscription events
3. Re-check `GET /billing/subscription/status`
4. Expect `data.trial.active_plan=true`

D) Confirm trial hard-stop is bypassed
- If the establishment is beyond day 4, online booking and reminders should work again because `trial.active_plan=true`.

## 5) Local webhook testing (two options)

Option 1: Stripe CLI (recommended)
- Install Stripe CLI
- Run:
  - `stripe login`
  - `stripe listen --forward-to http://localhost:8000/billing/stripe/webhook`
- Stripe CLI prints `whsec_...` for local use.

Option 2: Ngrok
- Expose local backend:
  - `ngrok http 8000`
- Set webhook URL in Stripe to the `https://....ngrok.io/billing/stripe/webhook`

## Troubleshooting

- Webhook returns 400 “Invalid webhook”:
  - `STRIPE_WEBHOOK_SECRET` missing or wrong
  - Stripe is not sending the `stripe-signature` header (proxy stripping headers)

- Subscription paid but `trial.active_plan` stays false:
  - Ensure subscription events are enabled
  - Ensure the subscription metadata contains `estabelecimento_id` (checkout sets this)

- Billing portal button not shown:
  - `customer_id` is only stored after a webhook runs. Finish a checkout (or wait for events) and reload.
