import uuid
from django.db import models
from django.conf import settings


class Plan(models.Model):
    """
    Represents a Stripe billing plan (monthly/yearly).
    Plans are created manually in Stripe dashboard and synced here.
    """
    INTERVAL_MONTHLY = 'month'
    INTERVAL_YEARLY = 'year'
    INTERVAL_CHOICES = [
        (INTERVAL_MONTHLY, 'Monthly'),
        (INTERVAL_YEARLY, 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    stripe_price_id = models.CharField(max_length=255, unique=True, db_index=True)
    stripe_product_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default=INTERVAL_MONTHLY)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'plans'
        ordering = ['amount']

    def __str__(self):
        return f"{self.name} — ${self.amount}/{self.interval}"


class Subscription(models.Model):
    """
    Tracks a user's Stripe subscription.
    One user = one subscription record (status changes over time).
    """
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CANCELED = 'canceled'
    STATUS_PAST_DUE = 'past_due'
    STATUS_TRIALING = 'trialing'
    STATUS_UNPAID = 'unpaid'
    STATUS_INCOMPLETE = 'incomplete'
    STATUS_INCOMPLETE_EXPIRED = 'incomplete_expired'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_PAST_DUE, 'Past Due'),
        (STATUS_TRIALING, 'Trialing'),
        (STATUS_UNPAID, 'Unpaid'),
        (STATUS_INCOMPLETE, 'Incomplete'),
        (STATUS_INCOMPLETE_EXPIRED, 'Incomplete Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions',
    )
    stripe_subscription_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True, db_index=True
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_INACTIVE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'

    def __str__(self):
        return f"{self.user.email} — {self.status}"

    @property
    def is_active(self):
        return self.status in (self.STATUS_ACTIVE, self.STATUS_TRIALING)


class PaymentHistory(models.Model):
    """
    Immutable log of every payment event from Stripe webhooks.
    """
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_PENDING = 'pending'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_history',
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='usd')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_history'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} — ${self.amount} — {self.status}"
