from django.test import Client, TestCase
from accounts.models import User
import json

def create_user(client):
    client.post('/rest-auth/registration/', {
        'email': 'test@example.com',
        'username': 'test@example.com',
        'password1': 'fooooo112345',
        'password2': 'fooooo112345'
    })

def get_tokens(client):
    response = client.post('/api/token/', {
        'email': 'test@example.com',
        'username': 'test@example.com',
        'password': 'fooooo112345',
    })
    data = json.loads(response.content)
    return {
        'access': data['access'],
        'refresh': data['refresh']
    }

class AuthenticationTestCase(TestCase):

    def setUp(self):
        self.c = Client()

    def test_registration(self):
        response = self.c.post('/rest-auth/registration/', {
            'email': 'test@example.com',
            'username': 'test@example.com',
            'password1': 'fooooo112345',
            'password2': 'fooooo112345'
        })
        data = json.loads(response.content)
        self.assertTrue(data['key'])

    def test_login(self):
        create_user(self.c)
        response = self.c.post('/api/token/', {
            'email': 'test@example.com',
            'username': 'test@example.com',
            'password': 'fooooo112345',
        })
        data = json.loads(response.content)
        self.assertTrue(data['access'])
        self.assertTrue(data['refresh'])


class SubscriberTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        create_user(self.c)
        tokens = get_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_get_subscriber_if_token_provided(self):
        response = self.c_auth.get('/api/v1/subscriber/me/')
        data = json.loads(response.content)