from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import Plan, Subscription

User = get_user_model()

PLANS_URL = '/api/subscriptions/plans/'
CREATE_URL = '/api/subscriptions/create/'
STATUS_URL = '/api/subscriptions/status/'
CANCEL_URL = '/api/subscriptions/cancel/'


def create_user(email='sub@example.com', username='subuser', password='Pass1234!'):
    return User.objects.create_user(email=email, username=username, password=password)


def create_plan(**kwargs):
    defaults = {
        'name': 'Pro',
        'stripe_price_id': 'price_test_123',
        'amount': '9.99',
        'interval': 'month',
    }
    defaults.update(kwargs)
    return Plan.objects.create(**defaults)


class PlanListTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)

    def test_list_plans(self):
        create_plan()
        res = self.client.get(PLANS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data['results']), 1)

    def test_inactive_plans_excluded(self):
        create_plan(name='Hidden', stripe_price_id='price_hidden', is_active=False)
        res = self.client.get(PLANS_URL)
        names = [p['name'] for p in res.data['results']]
        self.assertNotIn('Hidden', names)


class SubscriptionStatusTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)

    def test_status_returns_inactive_by_default(self):
        res = self.client.get(STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'inactive')

    def test_status_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class CancelSubscriptionTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)
        self.plan = create_plan()

    def test_cancel_no_subscription(self):
        res = self.client.post(CANCEL_URL, {})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch('apps.subscriptions.views.stripe.Subscription.modify')
    def test_cancel_at_period_end(self, mock_modify):
        mock_modify.return_value = MagicMock()
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            stripe_subscription_id='sub_test',
            status='active',
        )
        with patch('apps.subscriptions.views.send_cancellation_email') as mock_email:
            mock_email.delay = MagicMock()
            res = self.client.post(CANCEL_URL, {'cancel_immediately': False})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        sub = Subscription.objects.get(user=self.user)
        self.assertTrue(sub.cancel_at_period_end)
