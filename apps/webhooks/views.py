import logging
import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from apps.subscriptions.models import Subscription, PaymentHistory
from tasks.email_tasks import (
    send_subscription_confirmation_email,
    send_payment_failed_email,
    log_webhook_event,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    POST /api/webhooks/stripe/

    Receives Stripe webhook events and dispatches to the appropriate handler.
    Stripe signature is verified using STRIPE_WEBHOOK_SECRET.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Webhook error: Invalid payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Webhook error: Invalid signature")
        return HttpResponse(status=400)

    event_type = event['type']
    data_obj = event['data']['object']

    logger.info(f"Stripe webhook received | type={event_type} | id={event['id']}")

    # Async audit log (non-blocking)
    log_webhook_event.delay(event_type, event['id'])

    HANDLERS = {
        'customer.subscription.created': _handle_subscription_created,
        'customer.subscription.updated': _handle_subscription_updated,
        'customer.subscription.deleted': _handle_subscription_deleted,
        'invoice.payment_succeeded': _handle_payment_succeeded,
        'invoice.payment_failed': _handle_payment_failed,
        'customer.subscription.trial_will_end': _handle_trial_will_end,
    }

    handler = HANDLERS.get(event_type)
    if handler:
        handler(data_obj)
    else:
        logger.debug(f"Unhandled webhook event type: {event_type}")

    return HttpResponse(status=200)


# ─── Event Handlers ───────────────────────────────────────────────────────────

def _handle_subscription_created(data):
    _sync_subscription_from_stripe(data)


def _handle_subscription_updated(data):
    _sync_subscription_from_stripe(data)


def _handle_subscription_deleted(data):
    """Stripe fires this when a subscription is fully deleted (not just canceled)."""
    try:
        sub = Subscription.objects.get(stripe_subscription_id=data['id'])
        sub.status = Subscription.STATUS_CANCELED
        sub.canceled_at = timezone.now()
        sub.save(update_fields=['status', 'canceled_at'])
        logger.info(f"Subscription {data['id']} marked canceled via webhook")
    except Subscription.DoesNotExist:
        logger.warning(f"Webhook: subscription {data['id']} not found in DB")


def _handle_payment_succeeded(data):
    """invoice.payment_succeeded — record payment + send confirmation email."""
    customer_id = data.get('customer')
    try:
        user = User.objects.get(stripe_customer_id=customer_id)
    except User.DoesNotExist:
        logger.warning(f"Webhook: no user with stripe_customer_id={customer_id}")
        return

    try:
        sub = Subscription.objects.get(user=user)
    except Subscription.DoesNotExist:
        sub = None

    amount_paid = data.get('amount_paid', 0) / 100

    PaymentHistory.objects.create(
        user=user,
        subscription=sub,
        stripe_invoice_id=data.get('id', ''),
        stripe_payment_intent_id=data.get('payment_intent', '') or '',
        amount=amount_paid,
        currency=data.get('currency', 'usd'),
        status=PaymentHistory.STATUS_SUCCEEDED,
        description=f"Invoice payment — {sub.plan.name if sub and sub.plan else 'Subscription'}",
    )

    send_subscription_confirmation_email.delay(
        user.email,
        user.full_name,
        sub.plan.name if sub and sub.plan else 'Subscription',
        str(amount_paid),
    )
    logger.info(f"Payment succeeded for {user.email}: ${amount_paid}")


def _handle_payment_failed(data):
    """invoice.payment_failed — record failure + send alert email."""
    customer_id = data.get('customer')
    try:
        user = User.objects.get(stripe_customer_id=customer_id)
    except User.DoesNotExist:
        logger.warning(f"Webhook: no user with stripe_customer_id={customer_id}")
        return

    sub = Subscription.objects.filter(user=user).first()

    PaymentHistory.objects.create(
        user=user,
        subscription=sub,
        stripe_invoice_id=data.get('id', ''),
        amount=data.get('amount_due', 0) / 100,
        currency=data.get('currency', 'usd'),
        status=PaymentHistory.STATUS_FAILED,
        description='Payment attempt failed',
    )

    send_payment_failed_email.delay(user.email, user.full_name)
    logger.info(f"Payment failed for {user.email}")


def _handle_trial_will_end(data):
    """customer.subscription.trial_will_end — fires 3 days before trial ends."""
    customer_id = data.get('customer')
    try:
        user = User.objects.get(stripe_customer_id=customer_id)
        logger.info(f"Trial ending soon for {user.email}")
        # Could fire a send_trial_ending_email.delay() here
    except User.DoesNotExist:
        logger.warning(f"Webhook: no user with stripe_customer_id={customer_id}")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sync_subscription_from_stripe(data):
    """
    Keep our DB in sync with Stripe's subscription object.
    Called on created + updated events.
    """
    stripe_sub_id = data['id']
    try:
        sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
    except Subscription.DoesNotExist:
        logger.warning(f"Webhook sync: subscription {stripe_sub_id} not found in DB")
        return

    sub.status = data.get('status', sub.status)
    sub.cancel_at_period_end = data.get('cancel_at_period_end', False)

    if data.get('current_period_start'):
        sub.current_period_start = timezone.datetime.fromtimestamp(
            data['current_period_start'], tz=timezone.utc
        )
    if data.get('current_period_end'):
        sub.current_period_end = timezone.datetime.fromtimestamp(
            data['current_period_end'], tz=timezone.utc
        )
    if data.get('canceled_at'):
        sub.canceled_at = timezone.datetime.fromtimestamp(
            data['canceled_at'], tz=timezone.utc
        )

    sub.save()
    logger.info(f"Synced subscription {stripe_sub_id} → status={sub.status}")
