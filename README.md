# SaaS Subscription Billing API

> Production-ready subscription billing backend built with **Django REST Framework**, **Stripe**, **Celery**, and **Docker**.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-red)](https://www.django-rest-framework.org)
[![Stripe](https://img.shields.io/badge/Stripe-Integrated-blueviolet)](https://stripe.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://docker.com)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLIENT / POSTMAN                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Django REST API (Gunicorn)                 │
│                                                             │
│  ┌──────────────┐  ┌───────────────────┐  ┌─────────────┐  │
│  │  /api/auth/  │  │ /api/subscriptions│  │/api/webhooks│  │
│  │  JWT Auth    │  │   Stripe Plans    │  │  Stripe     │  │
│  │  Register    │  │   Subscribe       │  │  Events     │  │
│  │  Login       │  │   Cancel          │  │             │  │
│  └──────────────┘  └───────────────────┘  └──────┬──────┘  │
└──────────────────────────────────┬────────────────┼─────────┘
                                   │                │
                    ┌──────────────▼──┐   ┌─────────▼────────┐
                    │   PostgreSQL    │   │   Celery Worker   │
                    │   (Users,       │   │   (Email Tasks,   │
                    │    Plans,       │   │    Webhook Logs)  │
                    │    Subs,        │   └─────────┬─────────┘
                    │    Payments)    │             │
                    └─────────────────┘   ┌─────────▼─────────┐
                                          │       Redis        │
                                          │   (Broker +        │
                                          │    Result Store)   │
                                          └───────────────────┘
                    ┌──────────────────────────────────────────┐
                    │              Stripe Platform              │
                    │  (Subscriptions, Invoices, Webhooks)     │
                    └──────────────────────────────────────────┘
```

---

## Features

| Feature | Details |
|---|---|
| **JWT Auth** | Register, Login, Logout, Token Refresh, Change Password |
| **Stripe Subscriptions** | Create subscription with PaymentMethod, monthly plans |
| **Webhook Handling** | payment_succeeded, payment_failed, sub created/updated/deleted |
| **Celery + Redis** | Background email tasks with retry logic |
| **Payment History** | Full audit log of every payment event |
| **API Docs** | Auto-generated Swagger UI at `/api/docs/` |
| **Docker** | Single `docker-compose up` gets everything running |
| **Render Deploy** | One-click `render.yaml` config |

---

## Tech Stack

- **Django 4.2** + **Django REST Framework 3.15**
- **djangorestframework-simplejwt** — JWT authentication
- **Stripe Python SDK** — Subscription billing
- **Celery 5.4** + **Redis 7** — Background task queue
- **PostgreSQL 15** — Production database
- **drf-spectacular** — OpenAPI 3 schema & Swagger UI
- **Gunicorn** + **WhiteNoise** — Production WSGI server
- **Docker** + **docker-compose** — Containerized deployment

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- Redis running locally (`redis-server`) OR use Docker

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/django-saas-subscription-billing-api.git
cd django-saas-subscription-billing-api

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Stripe test keys and email config
```

### 3. Run Migrations & Start Server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Start Celery Worker (separate terminal)

```bash
celery -A config.celery_app worker --loglevel=info
```

### 5. Seed Test Plans

```bash
python manage.py shell
```
```python
from apps.subscriptions.models import Plan

Plan.objects.create(
    name="Starter",
    stripe_price_id="price_YOUR_STRIPE_PRICE_ID",
    amount="9.99",
    interval="month",
    features=["5 projects", "10 GB storage", "Email support"],
)
```

---

## Docker Setup

```bash
# Copy and fill environment variables
cp .env.example .env

# Build and start all services (API + PostgreSQL + Redis + Celery)
docker-compose up --build

# Run migrations (first time only)
docker-compose exec api python manage.py migrate
docker-compose exec api python manage.py createsuperuser
```

Runs on: `http://localhost:8000`

---

## API Endpoints

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/register/` | No | Register new user, get JWT tokens |
| `POST` | `/api/auth/login/` | No | Login, get JWT tokens |
| `POST` | `/api/auth/logout/` | Yes | Blacklist refresh token |
| `POST` | `/api/auth/token/refresh/` | No | Refresh access token |
| `GET` | `/api/auth/profile/` | Yes | Get current user profile |
| `PATCH` | `/api/auth/profile/` | Yes | Update profile (name fields) |
| `POST` | `/api/auth/change-password/` | Yes | Change password |

### Subscriptions

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/subscriptions/plans/` | Yes | List available plans |
| `POST` | `/api/subscriptions/create/` | Yes | Create a new subscription |
| `GET` | `/api/subscriptions/status/` | Yes | Get current subscription status |
| `POST` | `/api/subscriptions/cancel/` | Yes | Cancel subscription |
| `POST` | `/api/subscriptions/reactivate/` | Yes | Undo scheduled cancellation |
| `GET` | `/api/subscriptions/payments/` | Yes | List payment history |

### Webhooks

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/webhooks/stripe/` | Stripe sig | Receive Stripe events |

### Docs

| URL | Description |
|-----|-------------|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | Raw OpenAPI JSON |

---

## Request / Response Examples

### Register
```http
POST /api/auth/register/
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!"
}
```
```json
{
  "message": "Registration successful.",
  "user": { "id": "...", "email": "user@example.com", "subscription_status": "inactive" },
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

### Create Subscription
```http
POST /api/subscriptions/create/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "plan_id": "uuid-of-plan",
  "payment_method_id": "pm_card_visa"
}
```
```json
{
  "message": "Subscription created.",
  "subscription": {
    "status": "active",
    "plan": { "name": "Starter", "amount": "9.99", "interval": "month" },
    "current_period_end": "2026-03-25T12:00:00Z",
    "cancel_at_period_end": false
  }
}
```

### Cancel Subscription
```http
POST /api/subscriptions/cancel/
Authorization: Bearer <access_token>
Content-Type: application/json

{ "cancel_immediately": false }
```
```json
{
  "message": "Subscription canceled.",
  "subscription": { "status": "active", "cancel_at_period_end": true }
}
```

---

## Stripe Webhook Setup

1. Install Stripe CLI:
   ```bash
   brew install stripe/stripe-cli/stripe
   stripe login
   ```

2. Forward webhooks to local server:
   ```bash
   stripe listen --forward-to localhost:8000/api/webhooks/stripe/
   ```

3. Copy the webhook signing secret shown and set it in `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

**Handled events:**

| Stripe Event | Action |
|---|---|
| `customer.subscription.created` | Sync subscription to DB |
| `customer.subscription.updated` | Sync status changes |
| `customer.subscription.deleted` | Mark subscription canceled |
| `invoice.payment_succeeded` | Record payment + send confirmation email |
| `invoice.payment_failed` | Record failure + send alert email |
| `customer.subscription.trial_will_end` | Log event (extend for trial email) |

---

## Deploy to Render

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → **Blueprint**
3. Connect your GitHub repo — Render reads `render.yaml` automatically
4. Set secret env vars in Render Dashboard:
   - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
   - `ALLOWED_HOSTS` → `your-app.onrender.com`
   - `FRONTEND_URL` → your frontend domain
5. Add webhook endpoint in Stripe Dashboard:
   `https://your-app.onrender.com/api/webhooks/stripe/`

---

## Running Tests

```bash
python manage.py test apps.accounts apps.subscriptions
```

---

## Background Tasks (Celery)

| Task | Trigger | Retries |
|------|---------|---------|
| `send_welcome_email` | User registers | 3x (60s delay) |
| `send_subscription_confirmation_email` | Payment succeeds | 3x (60s delay) |
| `send_cancellation_email` | User cancels | 3x (60s delay) |
| `send_payment_failed_email` | Payment fails | 3x (60s delay) |
| `log_webhook_event` | Every webhook | None |

---

## Project Structure

```
django-saas-subscription-billing-api/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── development.py   # SQLite + console email
│   │   └── production.py    # PostgreSQL + security headers
│   ├── celery_app.py        # Celery configuration
│   └── urls.py              # Root URL routing
│
├── apps/
│   ├── accounts/            # JWT auth (register/login/profile)
│   │   ├── models.py        # Custom User model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── subscriptions/       # Stripe plans + billing logic
│   │   ├── models.py        # Plan, Subscription, PaymentHistory
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   └── webhooks/            # Stripe event handlers
│       ├── views.py
│       └── urls.py
│
├── tasks/
│   └── email_tasks.py       # Celery background tasks
│
├── Dockerfile               # Multi-stage production build
├── docker-compose.yml       # Local dev stack
├── render.yaml              # Render.com deployment config
├── requirements.txt
└── .env.example
```
