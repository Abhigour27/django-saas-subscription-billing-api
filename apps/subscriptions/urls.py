from django.urls import path
from .views import (
    PlanListView,
    CreateSubscriptionView,
    SubscriptionStatusView,
    CancelSubscriptionView,
    ReactivateSubscriptionView,
    PaymentHistoryView,
)

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('create/', CreateSubscriptionView.as_view(), name='subscription-create'),
    path('status/', SubscriptionStatusView.as_view(), name='subscription-status'),
    path('cancel/', CancelSubscriptionView.as_view(), name='subscription-cancel'),
    path('reactivate/', ReactivateSubscriptionView.as_view(), name='subscription-reactivate'),
    path('payments/', PaymentHistoryView.as_view(), name='payment-history'),
]
