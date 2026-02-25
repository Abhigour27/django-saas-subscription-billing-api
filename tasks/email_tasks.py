"""
Celery background tasks for email notifications and event logging.

All email tasks use bind=True + max_retries for resilience.
Failures are retried with exponential backoff via default_retry_delay.
"""
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email(self, email: str, name: str):
    """
    Fired after a new user registers.
    Sends an onboarding welcome email.
    """
    try:
        send_mail(
            subject='Welcome to SaaS App!',
            message=(
                f"Hi {name},\n\n"
                "Welcome to SaaS App! We're excited to have you on board.\n\n"
                "Get started by choosing a subscription plan:\n"
                f"{settings.FRONTEND_URL}/plans\n\n"
                "If you have any questions, reply to this email.\n\n"
                "Best,\nThe SaaS App Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"[EMAIL] Welcome email sent → {email}")
    except Exception as exc:
        logger.error(f"[EMAIL] Failed to send welcome email to {email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_subscription_confirmation_email(self, email: str, name: str, plan_name: str, amount: str):
    """
    Fired after invoice.payment_succeeded webhook.
    Confirms the user's subscription is now active.
    """
    try:
        send_mail(
            subject='Your Subscription is Active — SaaS App',
            message=(
                f"Hi {name},\n\n"
                "Your subscription has been activated.\n\n"
                f"  Plan   : {plan_name}\n"
                f"  Amount : ${amount}\n\n"
                "You now have full access to all features.\n\n"
                f"Manage your subscription: {settings.FRONTEND_URL}/dashboard/subscription\n\n"
                "Best,\nThe SaaS App Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"[EMAIL] Subscription confirmation sent → {email}")
    except Exception as exc:
        logger.error(f"[EMAIL] Failed to send confirmation email to {email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_cancellation_email(self, email: str, name: str, period_end: str = None):
    """
    Fired after the user cancels their subscription.
    Informs them of when access ends.
    """
    try:
        access_msg = (
            f"\nYour access continues until: {period_end}\n"
            if period_end else "\nYour access has ended immediately.\n"
        )
        send_mail(
            subject='Subscription Canceled — SaaS App',
            message=(
                f"Hi {name},\n\n"
                "Your subscription has been canceled."
                f"{access_msg}\n"
                "Changed your mind? Reactivate anytime:\n"
                f"{settings.FRONTEND_URL}/dashboard/subscription\n\n"
                "We'd love to hear your feedback:\n"
                f"{settings.FRONTEND_URL}/feedback\n\n"
                "Best,\nThe SaaS App Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"[EMAIL] Cancellation email sent → {email}")
    except Exception as exc:
        logger.error(f"[EMAIL] Failed to send cancellation email to {email}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payment_failed_email(self, email: str, name: str):
    """
    Fired after invoice.payment_failed webhook.
    Prompts user to update payment method.
    """
    try:
        send_mail(
            subject='Payment Failed — Action Required — SaaS App',
            message=(
                f"Hi {name},\n\n"
                "We were unable to process your payment.\n\n"
                "Please update your payment method to avoid service interruption:\n"
                f"{settings.FRONTEND_URL}/dashboard/billing\n\n"
                "Need help? Reply to this email.\n\n"
                "Best,\nThe SaaS App Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"[EMAIL] Payment failed email sent → {email}")
    except Exception as exc:
        logger.error(f"[EMAIL] Failed to send payment-failed email to {email}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def log_webhook_event(event_type: str, event_id: str):
    """
    Lightweight async audit log for every received Stripe webhook.
    Non-critical — no retries needed.
    """
    logger.info(f"[WEBHOOK] type={event_type} | id={event_id}")
