from rest_framework import serializers
from .models import Plan, Subscription, PaymentHistory


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = (
            'id', 'name', 'description', 'stripe_price_id',
            'amount', 'currency', 'interval', 'features',
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            'id', 'plan', 'stripe_subscription_id', 'status', 'is_active',
            'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'canceled_at',
            'created_at', 'updated_at',
        )
        read_only_fields = fields


class PaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentHistory
        fields = (
            'id', 'stripe_payment_intent_id', 'stripe_invoice_id',
            'amount', 'currency', 'status', 'description', 'created_at',
        )
        read_only_fields = fields


class CreateSubscriptionSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    payment_method_id = serializers.CharField(max_length=255)


class CancelSubscriptionSerializer(serializers.Serializer):
    cancel_immediately = serializers.BooleanField(default=False)
