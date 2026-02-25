from django.contrib import admin
from .models import Plan, Subscription, PaymentHistory


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'currency', 'interval', 'stripe_price_id', 'is_active')
    list_filter = ('interval', 'is_active', 'currency')
    search_fields = ('name', 'stripe_price_id', 'stripe_product_id')
    readonly_fields = ('id', 'created_at')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'plan', 'status', 'cancel_at_period_end',
        'current_period_end', 'created_at',
    )
    list_filter = ('status', 'cancel_at_period_end', 'created_at')
    search_fields = ('user__email', 'stripe_subscription_id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'plan')


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'currency', 'status', 'stripe_invoice_id', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('user__email', 'stripe_payment_intent_id', 'stripe_invoice_id')
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('user', 'subscription')
