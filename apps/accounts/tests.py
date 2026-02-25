from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()

REGISTER_URL = '/api/auth/register/'
LOGIN_URL = '/api/auth/login/'
PROFILE_URL = '/api/auth/profile/'


def create_user(**kwargs):
    defaults = {
        'email': 'test@example.com',
        'username': 'testuser',
        'password': 'StrongPassword123!',
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class AuthRegistrationTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_register_success(self):
        payload = {
            'email': 'new@example.com',
            'username': 'newuser',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        res = self.client.post(REGISTER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', res.data)
        self.assertIn('access', res.data['tokens'])
        self.assertIn('refresh', res.data['tokens'])

    def test_register_duplicate_email(self):
        create_user(email='dup@example.com', username='dup1')
        payload = {
            'email': 'dup@example.com',
            'username': 'dup2',
            'password': 'StrongPassword123!',
            'password_confirm': 'StrongPassword123!',
        }
        res = self.client.post(REGISTER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        payload = {
            'email': 'pw@example.com',
            'username': 'pwuser',
            'password': 'StrongPassword123!',
            'password_confirm': 'WrongPassword456!',
        }
        res = self.client.post(REGISTER_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class AuthLoginTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()

    def test_login_success(self):
        res = self.client.post(LOGIN_URL, {
            'email': 'test@example.com',
            'password': 'StrongPassword123!',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', res.data)

    def test_login_wrong_password(self):
        res = self.client.post(LOGIN_URL, {
            'email': 'test@example.com',
            'password': 'WrongPassword!',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_requires_auth(self):
        res = self.client.get(PROFILE_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(PROFILE_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['email'], self.user.email)
