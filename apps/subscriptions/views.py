import logging
import stripe
from django.conf import settings
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Plan, Subscription, PaymentHistory
from .serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    PaymentHistorySerializer,
    CreateSubscriptionSerializer,
    CancelSubscriptionSerializer,
)
from tasks.email_tasks import send_subscription_confirmation_email, send_cancellation_email

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class PlanListView(generics.ListAPIView):
    """
    GET /api/subscriptions/plans/
    List all active subscription plans.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)


class CreateSubscriptionView(APIView):
    """
    POST /api/subscriptions/create/
    Create a new Stripe subscription for the authenticated user.

    Body:
        plan_id          (UUID)   — ID of the Plan object
        payment_method_id (str)  — Stripe PaymentMethod ID (pm_...)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        payment_method_id = serializer.validated_data['payment_method_id']

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Block double subscriptions
        existing = Subscription.objects.filter(
            user=request.user,
            status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING],
        ).first()
        if existing:
            return Response(
                {'error': 'You already have an active subscription.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = request.user

            # 1. Create or fetch Stripe customer
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.full_name,
                    metadata={'user_id': str(user.id)},
                )
                user.stripe_customer_id = customer.id
                user.save(update_fields=['stripe_customer_id'])

            # 2. Attach payment method to customer
            stripe.PaymentMethod.attach(payment_method_id, customer=user.stripe_customer_id)

            # 3. Set it as the default payment method
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={'default_payment_method': payment_method_id},
            )

            # 4. Create the subscription
            stripe_sub = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[{'price': plan.stripe_price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent'],
                metadata={'user_id': str(user.id), 'plan_id': str(plan.id)},
            )

            # 5. Persist to DB
            subscription, _ = Subscription.objects.get_or_create(user=user)
            subscription.plan = plan
            subscription.stripe_subscription_id = stripe_sub.id
            subscription.status = stripe_sub.status

            if stripe_sub.current_period_start:
                subscription.current_period_start = timezone.datetime.fromtimestamp(
                    stripe_sub.current_period_start, tz=timezone.utc
                )
            if stripe_sub.current_period_end:
                subscription.current_period_end = timezone.datetime.fromtimestamp(
                    stripe_sub.current_period_end, tz=timezone.utc
                )
            subscription.save()

            response_data = {
                'message': 'Subscription created.',
                'subscription': SubscriptionSerializer(subscription).data,
            }

            # If payment requires 3DS confirmation, surface the client_secret
            if stripe_sub.status == Subscription.STATUS_INCOMPLETE:
                latest_invoice = stripe_sub.latest_invoice
                if latest_invoice and latest_invoice.payment_intent:
                    response_data['client_secret'] = latest_invoice.payment_intent.client_secret

            logger.info(f"Subscription created for {user.email}: {stripe_sub.id}")
            return Response(response_data, status=status.HTTP_201_CREATED)

        except stripe.error.CardError as e:
            return Response({'error': e.user_message}, status=status.HTTP_402_PAYMENT_REQUIRED)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error for {request.user.email}: {e}")
            return Response({'error': 'Payment processing failed. Please try again.'}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionStatusView(generics.RetrieveAPIView):
    """
    GET /api/subscriptions/status/
    Return the authenticated user's current subscription.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get_object(self):
        subscription, _ = Subscription.objects.get_or_create(
            user=self.request.user,
            defaults={'status': Subscription.STATUS_INACTIVE},
        )
        return subscription


class CancelSubscriptionView(APIView):
    """
    POST /api/subscriptions/cancel/
    Cancel the authenticated user's subscription.

    Body:
        cancel_immediately (bool) — default false (cancel at period end)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancel_immediately = serializer.validated_data['cancel_immediately']

        try:
            subscription = Subscription.objects.get(
                user=request.user,
                status__in=[Subscription.STATUS_ACTIVE, Subscription.STATUS_TRIALING],
            )
        except Subscription.DoesNotExist:
            return Response({'error': 'No active subscription found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            if cancel_immediately:
                stripe.Subscription.cancel(subscription.stripe_subscription_id)
                subscription.status = Subscription.STATUS_CANCELED
                subscription.canceled_at = timezone.now()
            else:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                )
                subscription.cancel_at_period_end = True

            subscription.save()

            # Background email notification
            send_cancellation_email.delay(
                request.user.email,
                request.user.full_name,
                str(subscription.current_period_end) if subscription.current_period_end else None,
            )

            logger.info(f"Subscription canceled for {request.user.email} (immediate={cancel_immediately})")
            return Response({
                'message': 'Subscription canceled.',
                'subscription': SubscriptionSerializer(subscription).data,
            })

        except stripe.error.StripeError as e:
            logger.error(f"Cancel error for {request.user.email}: {e}")
            return Response({'error': 'Failed to cancel subscription.'}, status=status.HTTP_400_BAD_REQUEST)


class ReactivateSubscriptionView(APIView):
    """
    POST /api/subscriptions/reactivate/
    Undo a scheduled cancellation (cancel_at_period_end → False).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            subscription = Subscription.objects.get(
                user=request.user,
                cancel_at_period_end=True,
            )
        except Subscription.DoesNotExist:
            return Response(
                {'error': 'No subscription scheduled for cancellation.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False,
            )
            subscription.cancel_at_period_end = False
            subscription.save()

            logger.info(f"Subscription reactivated for {request.user.email}")
            return Response({
                'message': 'Subscription reactivated.',
                'subscription': SubscriptionSerializer(subscription).data,
            })

        except stripe.error.StripeError as e:
            return Response({'error': 'Failed to reactivate subscription.'}, status=status.HTTP_400_BAD_REQUEST)


class PaymentHistoryView(generics.ListAPIView):
    """
    GET /api/subscriptions/payments/
    List payment history for the authenticated user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentHistorySerializer

    def get_queryset(self):
        return PaymentHistory.objects.filter(user=self.request.user)
