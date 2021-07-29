from operator import le, truediv
import re
from django.test import Client, TestCase
from djmoney.money import Money
from accounts.models import User
from subscribers.models import Subscriber, Subscription
from instructor.models import Coach, CoachApplication
from projects.models import Project, Milestone
from comments.models import Comment
from posts.models import Post
import json

def create_user(client):
    response = client.post('/rest-auth/registration/', {
        'email': 'test@example.com',
        'username': 'test@example.com',
        'password1': 'fooooo112345',
        'password2': 'fooooo112345'
    })
    return Subscriber.objects.get(user__email='test@example.com')

def create_mentor(client):
    response = client.post('/rest-auth/registration/', {
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
    return subscriber

    # coach = Coach.objects.create(user=subscriber.user, name=subscriber.name)

def create_mentor_2(client):
    response = client.post('/rest-auth/registration/', {
        'email': 'mentor2@example.com',
        'username': 'mentor2@example.com',
        'password1': 'fooooo112345',
        'password2': 'fooooo112345'
    })
    subscriber = Subscriber.objects.get(user__email='mentor2@example.com')
    # create a coach application with status accepted, this also creates a mentor account
    application = CoachApplication(subscriber=subscriber, message="testmessage")
    application.status = CoachApplication.APPROVED
    application.approved = True
    application.save()
    return subscriber

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

def get_mentor_2_tokens(client):
    response = client.post('/api/token/', {
        'email': 'mentor2@example.com',
        'username': 'mentor2@example.com',
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
        create_mentor_2(self.c)
        tokens = get_tokens(self.c)
        mentor_tokens = get_mentor_tokens(self.c)
        mentor_2_tokens = get_mentor_2_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.c_mentor_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_tokens['access']}")
        self.c_mentor_2_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_2_tokens['access']}")

    def test_create_post_as_subscriber_should_return_403(self):
        body = {
            'text': 'test text',
        }
        response = self.c_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 403)

    def test_create_post_as_mentor_should_return_201(self):
        coach = Coach.objects.get(user__email='mentor@example.com')
        body = {
            'tier': coach.tiers.first().id,
            'text': 'test text'
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['text'], 'test text')

    def test_create_post_as_mentor_without_tier_specified_should_return_400(self):
        body = {
            'text': 'test'
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        data = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(data['error'], 'A tier is required')

    def test_create_post_as_mentor_with_empty_body_should_return_400(self):
        response = self.c_mentor_auth.get('/api/v1/user/me/')
        data = json.loads(response.content)
        self.assertIn('coach', data[0])
        coach = Coach.objects.filter(surrogate=data[0]['coach']['surrogate']).first()

        body = {
            'tier': coach.tiers.first().id
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'Post contains no data')

    def test_create_post_as_mentor_with_invalid_tier_should_return_400(self):
        body = {
            'tier': 'test'
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(['Incorrect type. Expected pk value, received str.'], data['tier'])

    def test_create_post_as_mentor_with_other_mentors_tier_should_return_400(self):
        other_coach = Coach.objects.get(user__email='mentor2@example.com')

        body = {
            'text': 'test',
            'tier': other_coach.tiers.first().pk
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual('Invalid tier', data['error'])

    #TODO Create test cases for attached projects

class ProjectTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        create_user(self.c)
        create_mentor(self.c)
        tokens = get_tokens(self.c)
        mentor_tokens = get_mentor_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.c_mentor_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_tokens['access']}")

    def test_create_project_as_subscriber_should_return_403(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    'description': 'test',
                    'id': 1
                }
            ]
        }
        response = self.c_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 403)

    def test_update_project_as_subscriber_should_return_403(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    'description': 'test',
                    'id': 1
                }
            ]
        }
        response = self.c_auth.patch('/api/v1/projects/1/', data=body)
        self.assertEqual(response.status_code, 403)

    def create_test_project(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        data = response.json()
        return data

    def test_create_project_as_mentor_should_return_201(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 2)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 1)
        self.assertEqual(project.prerequisites.count(), 2)
        self.assertEqual(project.credit, Money(10, 'USD'))
    
    def test_create_project_as_mentor_without_name_should_return_400(self):
        body = {
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'A name is required')

    def test_create_project_as_mentor_without_description_should_return_400(self):
        body = {
            'name': 'Test project',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'A description is required')

    def test_create_project_as_mentor_without_difficulty_should_return_400(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'A difficulty is required')

    def test_create_project_as_mentor_without_milestones_should_return_400(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'At least one milestone is required')

    def test_create_project_as_mentor_with_wrong_milestone_format_should_return_400(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'One or more milestones are missing the "description" field')

    def test_create_project_as_mentor_with_milestone_with_empty_description_should_return_400(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'prerequisites': [
                '123',
                '456'
            ],
            'milestones': [
                {
                    "description": '',
                    "id": 1
                }
            ]
        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'One or more milestones are missing the "description" field')

    def test_create_project_as_mentor_with_no_prerequisites_should_return_201(self):
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 2,
            'credit': 10,
            'milestones': [
                {
                    "description": "test",
                    "id": 1
                }
            ]

        }
        response = self.c_mentor_auth.post('/api/v1/projects/', data=body)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 2)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 1)
        self.assertEqual(project.credit, Money(10, 'USD'))

    def test_update_project_as_mentor_should_return_200_with_updated_data(self):
        project = self.create_test_project()
        project = Project.objects.get(pk=project['id'])
        body = {
            'name': 'Test project',
            'description': 'test',
            'difficulty': 'AD',
            'team_size': 3,
            'credit': 11,
            'milestones': [
                {
                    "description": "test",
                }
            ]
        }
        response = self.c_mentor_auth.patch(f"/api/v1/projects/{str(project.surrogate)}/", data=body, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 3)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 2)
        self.assertEqual(project.credit, Money(11, 'USD'))

    def test_update_project_as_mentor_with_missing_data_should_return_200_with_updated_data(self):
        project = self.create_test_project()
        project = Project.objects.get(pk=project['id'])
        body = {
            'team_size': 3,
            'credit': 11,
            'milestones': [
                {
                    "description": "test",
                }
            ]
        }
        response = self.c_mentor_auth.patch(f"/api/v1/projects/{str(project.surrogate)}/", data=body, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 3)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 2)
        self.assertEqual(project.credit, Money(11, 'USD'))

    def test_update_project_as_mentor_with_existing_milestone_id_should_not_create_new_milestone_and_return_200_with_updated_data(self):
        project = self.create_test_project()
        project = Project.objects.get(pk=project['id'])
        body = {
            'team_size': 3,
            'credit': 11,
            'milestones': [
                {
                    "description": "test",
                    "id": str(project.milestones.first().surrogate),
                }
            ]
        }
        response = self.c_mentor_auth.patch(f"/api/v1/projects/{str(project.surrogate)}/", data=body, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 3)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 1)
        self.assertEqual(project.credit, Money(11, 'USD'))

    def test_update_project_as_mentor_with_prerequisites_should_delete_the_old_ones_and_create_new_ones_and_return_200_with_updated_data(self):
        project = self.create_test_project()
        project = Project.objects.get(pk=project['id'])
        # self.create_test_project creates a project with 2 prerequisites
        self.assertEqual(project.prerequisites.count(), 2)
        body = {
            'team_size': 3,
            'credit': 11,
            'prerequisites': [
                '123',
            ],
        }
        response = self.c_mentor_auth.patch(f"/api/v1/projects/{str(project.surrogate)}/", data=body, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Test project')
        self.assertEqual(data['difficulty'], 'AD')
        self.assertEqual(data['team_size'], 3)
        self.assertEqual(data['description'], 'test')
        project = Project.objects.get(pk=data['id'])
        self.assertEqual(project.milestones.count(), 1)
        self.assertEqual(project.prerequisites.count(), 1)
        self.assertEqual(project.credit, Money(11, 'USD'))

    def test_update_project_as_mentor_with_milestone_empty_description_should_return_400(self):
        project = self.create_test_project()
        project = Project.objects.get(pk=project['id'])
        # self.create_test_project creates a project with 2 prerequisites
        self.assertEqual(project.prerequisites.count(), 2)
        body = {
            'team_size': 3,
            'credit': 11,
            'prerequisites': [
                '123',
            ],
            'milestones': [
                {
                    "description": "",
                    "id": str(project.milestones.first().surrogate),
                }
            ]
        }
        response = self.c_mentor_auth.patch(f"/api/v1/projects/{str(project.surrogate)}/", data=body, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'One or more milestones are missing the "description" field')

    # def test_project_payment_sheet_without_subscription_should_400(self):
    #     project = self.create_test_project()
    #     project = Project.objects.get(pk=project['id'])
    #     response = self.c_auth.post(f"/api/v1/project_payment_sheet/{str(project.surrogate)}/", HTTP_ACCEPT='application/json', content_type="application/json")
    #     self.assertEqual(response.status_code, 400)
    #     data = response.json()
    #     self.assertEqual(data['error'], 'You need to be at least Tier 1 subsciber or above to join projects')

class CommentTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        self.user = create_user(self.c)
        self.mentor = create_mentor(self.c)
        self.mentor_2 = create_mentor_2(self.c)
        tokens = get_tokens(self.c)
        mentor_tokens = get_mentor_tokens(self.c)
        mentor_2_tokens = get_mentor_2_tokens(self.c)
        self.c_auth = Client(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.c_mentor_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_tokens['access']}")
        self.c_mentor_2_auth = Client(HTTP_AUTHORIZATION=f"Bearer {mentor_2_tokens['access']}")
        self.post = self.create_post()

    def create_post(self):
        coach = Coach.objects.get(user__email='mentor@example.com')
        body = {
            'tier': coach.tiers.first().id,
            'text': 'test text'
        }
        response = self.c_mentor_auth.post('/api/v1/posts/', data=body)
        return response.json()

    def test_comment_as_subscriber_without_being_subscribed_return_403(self):
        body = {
            'post': self.post['id'],
            'text': 'test text',
        }
        response = self.c_auth.post('/api/v1/comments/create/', data=body)
        self.assertEqual(response.status_code, 403)

    def test_comment_as_mentor_to_own_post_should_return_201(self):
        body = {
            'post': self.post['id'],
            'text': 'test text',
        }
        response = self.c_mentor_auth.post('/api/v1/comments/create/', data=body)
        self.assertEqual(response.status_code, 201)
    
    def test_comment_as_subscriber_being_subscribed_to_this_tier_return_201(self):
        post = Post.objects.get(surrogate=self.post['id'])
        subscription = Subscription.objects.create(subscriber=self.user, tier=post.tier, customer_id=self.user.customer_id)
        body = {
            'post': self.post['id'],
            'text': 'test text',
        }
        response = self.c_auth.post('/api/v1/comments/create/', data=body)
        self.assertEqual(response.status_code, 201)

