from operator import truediv
import re
from django.test import Client, TestCase
from accounts.models import User
from subscribers.models import Subscriber
from instructor.models import Coach, CoachApplication
import json

def create_user(client):
    client.post('/rest-auth/registration/', {
        'email': 'test@example.com',
        'username': 'test@example.com',
        'password1': 'fooooo112345',
        'password2': 'fooooo112345'
    })

def create_mentor(client):
    client.post('/rest-auth/registration/', {
        'email': 'mentor@example.com',
        'username': 'mentor@example.com',
        'password1': 'fooooo112345',
        'password2': 'fooooo112345'
    })
    subscriber = Subscriber.objects.get(user__email='mentor@example.com')
    # create a coach application with status accepted, this also creates a mentor account
    application = CoachApplication(subscriber=subscriber, message="testmessage")
    application.status = CoachApplication.APPROVED
    application.approved = True
    application.save()
    # coach = Coach.objects.create(user=subscriber.user, name=subscriber.name)

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

def get_mentor_tokens(client):
    response = client.post('/api/token/', {
        'email': 'mentor@example.com',
        'username': 'mentor@example.com',
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


class UserTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        create_user(self.c)
        create_mentor(self.c)
        tokens = get_tokens(self.c)
        mentor_tokens = get_mentor_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.c_mentor_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_tokens['access']}")

    def test_get_user_if_token_provided(self):
        response = self.c_auth.get('/api/v1/user/me/')
        data = json.loads(response.content)
        self.assertEqual(data[0]['email'], 'test@example.com')
        # the subscriber entity should be present on every user
        self.assertIn('subscriber', data[0])
        self.assertTrue(data[0]['subscriber']['id'])
        # if user is coach ensure that the coach entity is present
        if data[0]['is_coach']:
            self.assertIn('coach', data[0])
    
    def test_get_user_and_coach_if_token_provided(self):
        response = self.c_mentor_auth.get('/api/v1/user/me/')
        data = json.loads(response.content)
        self.assertEqual(data[0]['email'], 'mentor@example.com')
        # the subscriber entity should be present on every user
        self.assertIn('subscriber', data[0])
        self.assertTrue(data[0]['subscriber']['id'])
        # if user is coach ensure that the coach entity is present
        #if data['is_coach']:
        self.assertIn('coach', data[0])


class SubscriberTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        create_user(self.c)
        tokens = get_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_get_subscriber_if_token_provided(self):
        response = self.c_auth.get('/api/v1/subscriber/me/')
        data = json.loads(response.content)
        self.assertEqual(data['name'], 'test@example.com')
        self.assertTrue(data['id'])
    
    def test_return_401_unauthorized_if_token_not_provided(self):
        response = self.c.get('/api/v1/subscriber/me/')
        self.assertEqual(response.status_code, 401)


class PostTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        create_user(self.c)
        create_mentor(self.c)
        tokens = get_tokens(self.c)
        mentor_tokens = get_mentor_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.c_mentor_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_tokens['access']}")

    def test_create_post_as_subscriber_should_return_403(self):
        body = {
            'text': 'test text',
        }
        response = self.c_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 403)

    def test_create_post_as_coach_with_missing_tier_should_return_400(self):
        body = {
            'text': 'test text',
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'A tier is required')

    def test_create_post_as_coach_with_missing_properties_should_return_400(self):
        coach = Coach.objects.get(user__email='mentor@example.com')
        body = {
            'tier': coach.tiers.first().id,
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Post contains no data')

    def test_create_post(self):
        coach = Coach.objects.get(user__email='mentor@example.com')
        body = {
            'tier': coach.tiers.first().id,
            'text': 'test text'
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['text'], 'test text')
