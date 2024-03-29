from cmath import exp
import os
from collections import OrderedDict
from django.core.exceptions import ObjectDoesNotExist
import mux_python
from mux_python.rest import ApiException
from django.contrib.sites.models import Site
from django.conf import settings
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework import viewsets, mixins, permissions, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from rest_framework.decorators import parser_classes
from rest_framework.parsers import MultiPartParser, JSONParser
from django_filters import rest_framework as filters
from asgiref.sync import async_to_sync
from notifications.signals import notify
from notifications.models import Notification
from accounts.models import User
from subscribers.models import Subscriber, Subscription
from instructor.models import Coach, CoachApplication
from posts.models import Post, PostVideoAssetMetaData, PlaybackId, PostVideo
from projects.models import Project, Team, MilestoneCompletionReport, Milestone, MilestoneCompletionVideo, MilestoneCompletionVideoAssetMetaData, MilestoneCompletionPlaybackId, Coupon
from tiers.models import Tier
from expertisefields.models import ExpertiseField, ExpertiseFieldSuggestion
from comments.models import Comment
from reacts.models import React
from chat.models import ChatRoom, Message
from awards.models import Award, AwardBase
from qa.models import Question, QuestionInvitation, QaSession, AvailableTimeRange, CommonQuestion
from . import serializers
from .utils import extract_tags_from_question, create_meeting
import uuid
import stripe
import json
import channels.layers
import datetime
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


def get_user_posts(user):
    post_query = Post.objects.none()
    for coach in Coach.objects.filter(tiers__subscriptions__subscriber=user.subscriber).exclude(user=user):
        subscription = Subscription.objects.filter(
            subscriber=user.subscriber, tier__coach=coach).first()
        # by default get all posts available (except the ones that are chained to others, in that case just get the initial),
        # later we exclude posts based on the user subscription

        # UPDATE: all posts are free now so just return everything
        post_query |= coach.posts.exclude(parent_post__isnull=False)

        # # if use has subscriberd to tier 1 exclude tier 2 posts
        # if subscription.tier.tier==Tier.TIER1:
        #     post_query = post_query.exclude(coach=coach, tier__tier=Tier.TIER2)
        # elif subscription.tier.tier==Tier.FREE:
        #     post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])

    # user might not be a coach, in that case an exception is thrown
    try:
        post_query = post_query | Post.objects.filter(
            coach=user.coach).exclude(parent_post__isnull=False)
    except Exception:
        pass
    return post_query.distinct()


class IsCoach(permissions.BasePermission):
    message = "User must be a mentor"

    def has_permission(self, request, view):
        return request.user.is_coach


class IsSubscribedToPostTier(permissions.BasePermission):
    message = "User must be subscribed to specific tier"

    def has_permission(self, request, view):
        _id = request.data['post']
        post = Post.objects.filter(surrogate=_id)
        if not post.exists():
            return False
        post = post.first()
        post_tier = post.tier
        # check if user is the coach that created the post
        if request.user.is_coach:
            if request.user.coach == post_tier.coach:
                return True
        # else check if the user has subscribed to the tier this post belongs to
        return request.user.subscriber.subscriptions.filter(tier=post_tier).exists()

    def has_object_permission(self, request, view, obj):
        post_tier = obj.tier
        # check if user is the coach that created the post
        if request.user.is_coach:
            if request.user.coach == post_tier.coach:
                return True
        # else check if the user has subscribed to the tier this post belongs to
        return request.user.subscriber.subscriptions.filter(tier=post_tier).exists()


class CursorPaginationWithCount(CursorPagination):
    def paginate_queryset(self, queryset, request, view=None):
        self.count = self.get_count(queryset)
        return super().paginate_queryset(queryset, request, view)

    def get_count(self, queryset):
        """
        Determine an object count, supporting either querysets or regular lists.
        """
        try:
            return queryset.count()
        except (AttributeError, TypeError):
            return len(queryset)

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("count", self.count),
                    ("results", data),
                ]
            )
        )


class MessagePagination(CursorPagination):
    page_size = 20
    max_page_size = 100


class CommentPagination(CursorPaginationWithCount):
    page_size = 10
    max_page_size = 100


class PostPagination(CursorPaginationWithCount):
    page_size = 15
    max_page_size = 30


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


def send_notification_on_subscribe(subscriber, tier, subscription):
    channel_layer = channels.layers.get_channel_layer()
    notification_data = notify.send(subscriber, recipient=tier.coach.user,
                                    verb=f'Just subscribed on your {tier.label.lower()} tier!', action_object=subscription)

    notification = notification_data[0][1][0]
    async_to_sync(channel_layer.group_send)(
        f"{str(tier.coach.user.surrogate)}.notifications.group",
        {
            'type': 'send.notification',
            'id': notification.id
        }
    )


def send_notification_on_project_join(subscriber, project):
    channel_layer = channels.layers.get_channel_layer()
    notification_data = notify.send(
        subscriber, recipient=project.coach.user, verb=f'Just joined your project', action_object=project)

    notification = notification_data[0][1][0]
    async_to_sync(channel_layer.group_send)(
        f"{str(project.coach.user.surrogate)}.notifications.group",
        {
            'type': 'send.notification',
            'id': notification.id
        }
    )


class UserMeViewSet(mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.UserMeSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    # TODO FIX MEEEEE
    def get_serializer_class(self):
        # UserMeNoCoachSerializer
        user = self.get_queryset()
        print(user.first().is_coach)
        if user.first().is_coach:
            return serializers.UserMeSerializer
        return serializers.UserMeNoCoachSerializer

    def get_queryset(self):
        if not self.request.user:
            return HttpResponse(status=401)
        queryset = User.objects.filter(pk=self.request.user.pk)
        return queryset

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class SubscriberMeViewSet(APIView):
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        if self.action == 'update':
            return serializers.SubscriberUpdateSerializer
        return serializers.SubscriberSerializer

    def get_queryset(self):
        return Subscriber.objects.filter(user=self.request.user.pk)


class CoachFilterSet(filters.FilterSet):
    name = filters.CharFilter(field_name="name", lookup_expr="icontains")
    expertise = filters.CharFilter(
        field_name="expertise_field__name", lookup_expr="iexact")
    expertise_field = filters.ModelChoiceFilter(
        queryset=ExpertiseField.objects.all())

    class Meta:
        model = Coach
        fields = ['expertise_field', 'expertise', 'name']


class CoachViewSet(viewsets.ModelViewSet):
    queryset = Coach.objects.all()
    serializer_class = serializers.CoachSerializer
    #filterset_fields = ['expertise_field']
    filterset_class = CoachFilterSet
    lookup_field = 'surrogate'
    permission_classes_by_action = {'create': [permissions.IsAuthenticated],
                                    'update': [permissions.IsAuthenticated],
                                    'partial_update': [permissions.IsAuthenticated],
                                    'list': [permissions.AllowAny],
                                    'retrieve': [permissions.AllowAny]}

    def get_queryset(self):
        if self.action == 'list' or self.action == 'retrieve':
            queryset = Coach.objects.filter(charges_enabled=True)
        else:
            queryset = Coach.objects.all()

        username = self.request.query_params.get('username', None)
        return queryset

    def get_object(self):
        try:
            return Coach.objects.get(surrogate=self.kwargs.get('surrogate'))
        except ObjectDoesNotExist:
            raise Http404

    def get_permissions(self):
        try:
            # return permission_classes depending on `action`
            return [permission() for permission in self.permission_classes_by_action[self.action]]
        except KeyError:
            # action is not set return default permission_classes
            return [permission() for permission in self.permission_classes]

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class CoachApplicationViewSet(generics.CreateAPIView,
                              viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = CoachApplication.objects.all()
    serializer_class = serializers.CoachApplicationSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyCoachesViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.CoachSerializer

    def get_queryset(self):
        if self.request.user.is_coach:
            return Coach.objects.filter(tiers__subscriptions__subscriber=self.request.user.subscriber).exclude(user=self.request.user)
            # return self.request.user.coaches.exclude(user=self.request.user)
        return Coach.objects.filter(tiers__subscriptions__subscriber=self.request.user.subscriber)
        # return self.request.user.coaches.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyCouponsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.MyCouponSerializer

    def get_queryset(self):
        return Coupon.objects.filter(subscriber=self.request.user.subscriber)

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class PostViewSet(viewsets.GenericViewSet,
                  mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin):
    permission_classes = [permissions.IsAuthenticated,
                          IsCoach]  # IsSubscribedToPostTier
    # permission_classes_by_action = {'create': [permissions.IsAuthenticated, IsCoach],
    #                                 'list': [permissions.IsAuthenticated]}

    queryset = Post.objects.all()
    serializer_class = serializers.PostSerializer
    lookup_field = 'surrogate'

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.PostCreateSerializer
        return serializers.PostSerializer

    def get_queryset(self):
        # prevents chained posts from being displayed outside parent post
        return Post.objects.exclude(parent_post__isnull=False)

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class CoachPostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.PostSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        surrogate = self.kwargs['surrogate']
        coach = Coach.objects.filter(surrogate=surrogate).first()
        post_query = Post.objects.none()
        subscription = Subscription.objects.filter(
            subscriber=self.request.user.subscriber, tier__coach=coach).first()
        # by default get all posts available (except the ones that are chained to others, in that case just get the initial),
        # later we exclude posts based on the user subscription

        # UPDATE: all posts are free now so just give everything
        post_query |= coach.posts.exclude(parent_post__isnull=False)

        # if subscription:
        #     # if use has subscriberd to tier 1 exclude tier 2 posts
        #     if subscription.tier.tier==Tier.TIER1:
        #         post_query = post_query.exclude(coach=coach, tier__tier=Tier.TIER2)
        #     elif subscription.tier.tier==Tier.FREE:
        #         post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])
        # else:
        #     # if the user is the coach don't exclude anything
        #     if self.request.user != coach.user:
        #         post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])

        return post_query.distinct()


class ChainedPostsViewSet(generics.ListCreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainedPostsSerializer


class NewPostsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.PostSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        return get_user_posts(self.request.user)

    def get_serializer_context(self):
        return {
            'request': self.request
        }


class NewPosts2ViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.PostSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        user_posts = get_user_posts(self.request.user)
        if self.request.user.subscriber.last_seen_post:
            unseen_posts = user_posts.filter(
                created__gt=self.request.user.subscriber.last_seen_post.created)
            return unseen_posts
        return user_posts

    def get_serializer_context(self):
        return {
            'request': self.request
        }


class ChainPostsViewSet(generics.CreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.ChainPostsSerializer


class ProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    #permission_classes = [permissions.IsAuthenticated, ]
    lookup_field = 'surrogate'

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update' or self.action == 'partial_update':
            return serializers.CreateOrUpdateProjectSerializer
        return serializers.ProjectSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
        }

    def get_permissions(self):
        if self.action == 'create' or self.action == 'update' or self.action == 'partial_update':
            permission_classes = [permissions.IsAuthenticated, IsCoach]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class MyCoachesProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.MyProjectsSerializer

    def get_queryset(self):
        projects = Project.objects.none()
        for subscription in self.request.user.subscriber.subscriptions.all():
            projects |= subscription.tier.coach.created_projects.all()
        return projects.distinct()
        # return self.request.user.subscriber.projects.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.MyProjectsSerializer

    def get_queryset(self):
        return Project.objects.filter(teams__members=self.request.user.subscriber).distinct()
        # return self.request.user.subscriber.projects.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyCreatedProjectsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
        }

    def get_queryset(self):
        if self.request.user.is_coach:
            return self.request.user.coach.created_projects.all()
        else:
            return Project.objects.none()


class TeamsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TeamSerializer

    def get_queryset(self):
        project = self.kwargs['project_id']
        return Team.objects.filter(project__surrogate=project)

    def get_serializer_context(self):
        project = Project.objects.get(surrogate=self.kwargs['project_id'])
        return {
            'request': self.request,
            'project': project
        }


class ProjectPostsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.PostSerializer

    def get_queryset(self):
        project_id = self.kwargs['project_id']
        project = Project.objects.filter(surrogate=project_id).first()
        return project.posts.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class ExpertiseViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ExpertiseSerializer
    queryset = ExpertiseField.objects.all()


class MyTiersViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        if self.action == 'update' or self.action == 'partial_update':
            return serializers.UpdateTierSerializer
        else:
            return serializers.TierSerializer

    def get_queryset(self):
        if self.request.user.is_coach:
            return self.request.user.coach.tiers.all()
        else:
            return Tier.objects.none()


class MyTeamsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.MyTeamsSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_queryset(self):
        return self.request.user.subscriber.teams.all()


class CommentsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.CommentSerializer
    pagination_class = CommentPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.CreateCommentSerializer
        return serializers.CommentSerializer

    def get_queryset(self):
        post = self.kwargs['post_id']
        # get only top level comments
        return Post.objects.get(surrogate=post).comments.filter(level=0)

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class CreateCommentViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    serializer_class = serializers.CreateCommentSerializer
    pagination_class = CommentPagination
    queryset = Comment.objects.all()
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly, IsSubscribedToPostTier]

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class CommentRepliesViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.CommentSerializer
    pagination_class = CommentPagination

    def get_queryset(self):
        comment = self.kwargs['comment_id']
        return Comment.objects.get(surrogate=comment).children.all()


class ReactsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ReactSerializer
    queryset = React.objects.all()


class MilestoneCompletionReportViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin,
                                       mixins.RetrieveModelMixin, mixins.ListModelMixin,
                                       mixins.UpdateModelMixin):
    serializer_class = serializers.MilestoneCompletionReportSerializer
    queryset = MilestoneCompletionReport.objects.all()
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        if self.action == 'create':
            print(self.request.data)
            return serializers.CreateMilestoneCompletionReportSerializer
        # if self.action == 'partial_update' or self.action == 'update':
        #     milestone = Milestone.objects.get(id=self.kwargs['milestone_id'])
        #     user = self.request.user
        #     if user.coach and milestone.project.coach == user.coach:
        #         return serializers.CoachUpdateMilestoneCompletionReportSerializer
        #     else:
        #         # TODO
        #         # create another SubscriberUpdateMilestoneSerializer for subscribers to edit their report
        #         pass
        return serializers.MilestoneCompletionReportSerializer

    def get_queryset(self):
        milestone = Milestone.objects.filter(
            id=self.kwargs['milestone_id']).first()
        if milestone:
            return milestone.reports.all()
        return Milestone.objects.none()

    def get_serializer_context(self):
        return {
            'milestone_id': self.kwargs['milestone_id'],
        }


class MyChatRoomsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ChatRoomSerializer

    def get_queryset(self):
        return self.request.user.subscriber.chat_rooms.all()


class RoomMessagesViewSet(viewsets.ModelViewSet):
    pagination_class = MessagePagination
    serializer_class = serializers.MessageSerializer

    def get_queryset(self):
        return ChatRoom.objects.get(surrogate=self.kwargs['surrogate']).messages.all()


class CreateMessageViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    serializer_class = serializers.CreateMessageSerializer
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = Message.objects.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class AwardBaseViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = serializers.AwardBaseSerializer
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = AwardBase.objects.all()


class CreateAwardViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    serializer_class = serializers.CreateAwardSerializer
    queryset = AwardBase.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, ]

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyAwardsViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = serializers.AwardSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_queryset(self):
        subscriber = self.request.user.subscriber
        return subscriber.awards.all()


class MyQAInvitationsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.QuestionInvitationSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoach]

    def get_queryset(self):
        return self.request.user.coach.invitations.all()


class MyAssignedQuestions(viewsets.ModelViewSet):
    serializer_class = serializers.QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoach]

    def get_queryset(self):
        return self.request.user.coach.assigned_questions.all()


class MyUpcomingQuestions(viewsets.ModelViewSet):
    serializer_class = serializers.QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoach]

    def get_queryset(self):
        now = datetime.datetime.now()
        return self.request.user.coach.assigned_questions.filter(initial_delivery_time__gte=now)


class MyArchivedQuestions(viewsets.ModelViewSet):
    serializer_class = serializers.QuestionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoach]

    def get_queryset(self):
        now = datetime.datetime.now()
        return self.request.user.coach.assigned_questions.filter(initial_delivery_time__lte=now)


class NotificationsViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = serializers.NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_queryset(self):
        user = self.request.user
        return user.notifications.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def ask_question(request):
    '''
    Logic here should may be extracted to just question creation
    '''
    question_body = request.data.get('body')
    when = request.data.get('when')
    if when == 'now':
        delivery_time_estimate = datetime.datetime.now()
        question = Question.objects.create(
            body=question_body, initial_delivery_time=delivery_time_estimate, answer_needed_now=True)

        # tags = extract_tags_from_question(question)
        # find expertise in tags
        expertise = 'programming'
        coaches = Coach.objects.filter(expertise_field__name=expertise).all()
        for coach in coaches:

            # check if coach has SMS notifications enabled and send a SMS with the question
            # and a link to his questions dashboard

            # here send mandatory email with same stuff as the SMS
            pass

        serializer = serializers.QuestionSerializer(question)
        return Response({'question': serializer.data})

    elif when == '6' or when == '12' or when == '24':
        delivery_time_estimate = datetime.datetime.now() + datetime.timedelta(hours=int(when))
        question = Question.objects.create(
            body=question_body, initial_delivery_time=delivery_time_estimate)
        serializer = serializers.QuestionSerializer(question)
        return Response({'question': serializer.data})
    else:
        return Response({'error': 'This delivery time is not supported.'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def create_qa_checkout_session(request):
    qa_session_id = request.data.get('qa_session_id')
    question_id = request.data.get('question_id')
    qa_session = QaSession.objects.get(surrogate=qa_session_id)
    question = Question.objects.get(surrogate=question_id)
    price = stripe.Price.retrieve(qa_session.price_id)

    if os.environ.get('DEBUG') == 'True':
        success_url = 'http://localhost:3000/checkout?status=success'
        cancel_url = 'http://localhost:3000/checkout?status=canceled'
    else:
        success_url = 'https://questions.troosh.app/checkout?status=success'
        cancel_url = 'https://questions.troosh.app/checkout?status=canceled'

    checkout_session = stripe.checkout.Session.create(
        line_items=[
            {
                'price': qa_session.price_id,
                'quantity': 1,
            },
        ],
        metadata={'type': 'qa', 'id': qa_session_id,
                  'question_id': question_id},
        mode='payment',
        payment_intent_data={
            'application_fee_amount': int(price.unit_amount * 0.2),
            'transfer_data': {
                'destination': qa_session.coach.stripe_id,
            },
        },
        allow_promotion_codes=True,
        success_url=success_url,
        cancel_url=cancel_url
    )
    return Response({'checkout_url': checkout_session.url})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.AllowAny,))
def check_available_coaches_for_question(request, question_id):
    question = Question.objects.filter(surrogate=question_id).first()
    question_data = extract_tags_from_question(question.body)
    # let user be able to filter mentors based on their expertise
    expertise = request.query_params.get('expertise')
    enforced_expertise = True
    is_weak = question_data['is_weak']

    if not expertise:
        expertise = question_data['umbrella_term']
        enforced_expertise = False
    # if user enforced the expertise then don't mark results as weak
    # since we don't rely on the ml model to find the mentors
    if enforced_expertise:
        is_weak = False

    status = question_data['status']
    coaches = Coach.objects.filter(
        expertise_fields__name__iexact=expertise).all()
    available_coaches = Coach.objects.none()
    available_on_other_times = 0
    for coach in coaches:
        _coach = Coach.objects.filter(id=coach.id)
        if not question.answer_needed_now:
            # get the 1 hour range at the time the user wants the answer
            one_hour_after_delivery_time_estimate = question.initial_delivery_time + \
                datetime.timedelta(hours=1)

            # we then check if he has another question lined up during that time
            # since the ranges are not really percise we leave a 1 hour buffer to be safe that
            # no questions overlap with each other
            # in case he is free during that time range we can add him to the available coaches

            # the below query will extend over the coach's availability if the range window is small
            # for example if user requests 60 minutes and coach is available during 7:00-7:20
            # the query will be equal to false
            is_coach_available_during_that_time = coach.available_time_ranges.filter(
                start_time__lte=question.initial_delivery_time.time(), end_time__gte=question.initial_delivery_time.time()).exists()
            is_coach_booked_for_this_time = coach.assigned_questions.filter(delivery_time__range=[
                                                                            question.initial_delivery_time, one_hour_after_delivery_time_estimate]).exists()
            if not is_coach_available_during_that_time or is_coach_booked_for_this_time:
                available_on_other_times += 1
            if is_coach_available_during_that_time and not is_coach_booked_for_this_time:
                available_coaches = available_coaches | _coach
        else:
            invitation = QuestionInvitation.objects.filter(
                question=question, coach=coach)
            # Don't bother to send an invitation if the question is a hit or miss
            if not is_weak:
                if not invitation.exists():
                    # create an invitation
                    # this sends an email to each coach and informs him that a question needs an answer now
                    # they can then accept or decline the request
                    QuestionInvitation.objects.create(
                        question=question, coach=coach)
                    status = 'waiting_for_mentors'
                else:
                    invitation = invitation.first()
                    if invitation.status == QuestionInvitation.ACCEPTED:
                        available_coaches = available_coaches | _coach
                    elif invitation.status == QuestionInvitation.DECLINED:
                        available_on_other_times += 1
            else:
                status = 'error'
        # serializer = serializers.QuestionSerializer(question)
    coach_serializer = serializers.CoachSerializer(
        available_coaches, context={'request': request}, many=True)
    return Response({'available_coaches': coach_serializer.data, 'is_weak': is_weak, 'expertise': expertise,
                     'available_on_other_times': available_on_other_times, 'status': status})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated, IsCoach))
def respond_to_qa_invitation(request, invitation_id):
    coach = request.user.coach
    qa_invitation = QuestionInvitation.objects.filter(
        surrogate=invitation_id).first()
    response = request.data.get('response')
    if qa_invitation:
        if response == QuestionInvitation.ACCEPTED:
            qa_invitation.status = QuestionInvitation.ACCEPTED
        else:
            qa_invitation.status = QuestionInvitation.DECLINED
        qa_invitation.save()
        return Response({'status': 'ok'})
    else:
        return Response({'status': 'not found'})


# Allow anyone to do this so the mentor can accept without logging in
# He should be the only one to have this id anyways
@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny, ))
def accept_qa_invitation(request, invitation_id):
    qa_invitation = QuestionInvitation.objects.filter(
        surrogate=invitation_id).first()
    if qa_invitation:
        qa_invitation.status = QuestionInvitation.ACCEPTED
        return Response({'status': 'ok'})
    return Response({'status': 'an unexpected error occured'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated, IsCoach))
def change_common_questions(request):
    coach = request.user.coach
    common_questions = request.data
    if common_questions:
        coach.common_questions.all().delete()
        for question in common_questions:
            CommonQuestion.objects.create(body=question, coach=coach)
    return Response({'status': 'ok'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated, IsCoach))
def change_coach_qa_availability(request):
    coach = request.user.coach
    availability_ranges = request.data.get('availability_ranges')
    if availability_ranges:
        # just delete the old ones and add the new ones again
        coach.available_time_ranges.all().delete()
        for time_range in availability_ranges:
            weekday = time_range['weekday']
            start_time_hour = int(time_range['start_time'][:2])
            start_time_minutes = int(time_range['start_time'][3:5])
            end_time_hour = int(time_range['end_time'][:2])
            end_time_minutes = int(time_range['end_time'][3:5])
            AvailableTimeRange.objects.create(weekday=weekday, coach=coach,
                                              start_time=datetime.time(
                                                  hour=start_time_hour, minute=start_time_minutes),
                                              end_time=datetime.time(hour=end_time_hour, minute=end_time_minutes))
    return Response({'status': 'ok'})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_unread_count(request):
    return Response({'unread_count': request.user.notifications.unread().count()})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def mark_all_read(request):
    request.user.notifications.mark_all_as_read()
    return Response({'unread_count': request.user.notifications.unread().count()})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_unseen_posts(request):
    user = request.user
    user_posts = get_user_posts(user)
    if user.subscriber.last_seen_post:
        unseen_posts = user_posts.filter(
            created__gt=user.subscriber.last_seen_post.created)
        return Response({'unseen_posts': unseen_posts})
    return Response({'unseen_posts': user_posts})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_unseen_post_count(request):
    user = request.user
    user_posts = get_user_posts(user)
    if user.subscriber.last_seen_post:
        unseen_post_count = user_posts.filter(
            created__gt=user.subscriber.last_seen_post.created).count()
        return Response({'unseen_post_count': unseen_post_count})
    return Response({'unseen_post_count': user_posts.count()})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def mark_last_seen_post(request):
    user = request.user
    post_id = request.data['id']
    post = Post.objects.filter(surrogate=post_id)
    if post.exists():
        post = post.first()
        user.subscriber.last_seen_post = post
        user.subscriber.save()
        return Response({'last_seen_post': post_id})


@api_view(http_method_names=['GET', 'PATCH'])
@permission_classes((permissions.IsAuthenticated,))
def subscriber_me(request):
    user = request.user

    # this might be unnecessary since subcriber is accessible through user
    subscriber = Subscriber.objects.filter(user=user.pk).first()
    if request.method == 'GET':
        serializer = serializers.SubscriberSerializer(subscriber)
        return Response(serializer.data)
    elif request.method == 'PATCH':
        serializer = serializers.SubscriberUpdateSerializer(
            subscriber, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(http_method_names=['GET', 'PATCH'])
@permission_classes((permissions.IsAuthenticated,))
def coach_me(request):
    user = request.user

    # this might be unnecessary since subcriber is accessible through user
    coach = Coach.objects.filter(user=user.pk).first()
    if request.method == 'GET':
        serializer = serializers.CoachSerializer(
            coach, context={'request': request})
        return Response(serializer.data)
    elif request.method == 'PATCH':
        serializer = serializers.CoachSerializer(
            coach, context={'request': request}, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def handle_join_project(project, subscriber, request=None):
    team_found = False

    # First try to find a team with empty spots that has not started yet and add the user there
    for team in project.teams.all():
        has_started_progressing = team.milestone_completion_reports.count() > 0
        if team.members.count() < project.team_size and not has_started_progressing:
            team_found = True
            team.members.add(subscriber)

            # add the user to all available chat rooms for this project
            chat_rooms = ChatRoom.objects.filter(
                project=project, team=team)
            for chat_room in chat_rooms:
                chat_room.members.add(subscriber)

            # this function might be called from a webhook
            # if this is the case don't run this
            if request:
                return Response({'team': serializers.TeamSerializer(
                    team,
                    context={'request': request,
                             'project': project}).data})

    # If no empty teams are found / or created create a new team only with this member
    if not team_found:
        new_team = Team.objects.create(
            project=project, name=subscriber.name)
        new_team.members.add(subscriber)

        # create a new chat room for the team
        chat_room = ChatRoom.objects.create(name=subscriber.name, team=new_team,
                                            team_type=ChatRoom.TEAM, project=project)
        chat_room.members.add(subscriber)

        # also create another chat room for the team + the coach
        chat_room_with_coach = ChatRoom.objects.create(team=new_team,
                                                       name=subscriber.name, team_type=ChatRoom.TEAM_WITH_COACH, project=project)
        chat_room_with_coach.members.add(
            subscriber, project.coach.user.subscriber)
        if request:
            return Response({'team': serializers.TeamSerializer(
                new_team,
                context={'request': request,
                            'project': project}).data})
    send_notification_on_project_join(subscriber, project)


@api_view(http_method_names=['POST'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def project_payment_sheet(request, id):
    # Remember to check if user is a subscriber of tier 1+ here
    user = request.user
    project = Project.objects.filter(surrogate=id)
    if project.exists():
        project = project.first()
        ephemeralKey = stripe.EphemeralKey.create(
            customer=user.subscriber.customer_id,
            stripe_version='2020-08-27',
        )

        subscription = Subscription.objects.filter(
            subscriber=user.subscriber, tier__coach=project.coach)
        if not subscription.exists():
            return Response({'error': 'You need to be at least Tier 1 subsciber or above to join projects'})
        subscription = subscription.first()
        # if subscription.tier.tier == Tier.FREE:
        #     return Response({'error': 'Free tier subscribers cannot join projects'})
        invoice = None
        payment_intent = None
        coupon = Coupon.objects.filter(
            subscriber=request.user.subscriber, coach=project.coach)
        price = stripe.Price.retrieve(
            project.price_id,
        )
        if coupon.exists():
            coupon = coupon.first()
            if coupon.valid:
                # 100% discount is applied here, no need for stripe to do anything
                handle_join_project(project, request.user.subscriber, request)
                coupon.valid = False
                coupon.save()
                return Response({
                    'paymentIntent': payment_intent.client_secret if payment_intent else None,
                    'paymentIntentId': payment_intent.id if payment_intent else None,
                    'ephemeralKey': ephemeralKey.secret if ephemeralKey else None,
                    'customer': user.subscriber.customer_id
                })
        else:
            payment_intent = stripe.PaymentIntent.create(
                amount=price.unit_amount,
                currency="eur",
                customer=request.user.subscriber.customer_id,
                application_fee_amount=int(price.unit_amount * 0.2),
                transfer_data={
                    "destination": project.coach.stripe_id,
                },
                metadata={
                    'type': 'project',
                    'subscriber': request.user.subscriber.surrogate,
                    'troosh_status': 'created',
                    'id': project.surrogate,
                }
            )
            return Response({
                'paymentIntent': payment_intent.client_secret if payment_intent else None,
                'paymentIntentId': payment_intent.id if payment_intent else None,
                'ephemeralKey': ephemeralKey.secret if ephemeralKey else None,
                'customer': user.subscriber.customer_id
            })


@api_view(http_method_names=['POST'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def join_project(request, id):
    # Remember to check if user is a subscriber of tier 1+ here
    user = request.user
    project = Project.objects.filter(surrogate=id)
    if project.exists():
        project = project.first()
        # this will later be used for validation
        invoice = None

        # Do some tier validation here
        subscription = Subscription.objects.filter(
            subscriber=user.subscriber, tier__coach=project.coach)
        if not subscription.exists():
            return Response({'error': 'You need to be at least Tier 1 subsciber or above to join projects'})
        subscription = subscription.first()
        if subscription.tier.tier == Tier.FREE:
            return Response({'error': 'Free tier subscribers cannot join projects'})
        elif subscription.tier.tier == Tier.TIER1:
            coupon = Coupon.objects.filter(
                subscriber=request.user.subscriber, coach=project.coach)

            if coupon.exists():
                coupon = coupon.first()
                try:
                    price = stripe.Price.retrieve(
                        project.price_id,
                    )
                    if coupon.valid:
                        invoice_item = stripe.InvoiceItem.create(
                            customer=request.user.subscriber.customer_id,
                            price=project.price_id,
                            currency="eur",
                            # amount=price.unit_amount,
                            discounts=[{
                                'coupon': coupon.coupon_id,
                            }],
                        )

                        # using int rounds down
                        invoice = stripe.Invoice.create(
                            customer=request.user.subscriber.customer_id,
                            application_fee_amount=int(
                                price.unit_amount * 0.2),
                            transfer_data={
                                "destination": project.coach.stripe_id,
                            },
                        )

                        invoice = stripe.Invoice.pay(invoice.id)

                        # disable coupon after using it
                        coupon.valid = False
                        coupon.save()
                    else:
                        invoice_item = stripe.InvoiceItem.create(
                            customer=request.user.subscriber.customer_id,
                            price=project.price_id,
                            # amount=price.unit_amount,
                            currency="eur",
                        )

                        # using int rounds down
                        invoice = stripe.Invoice.create(
                            customer=request.user.subscriber.customer_id,
                            application_fee_amount=int(
                                price.unit_amount * 0.2),
                            transfer_data={
                                "destination": project.coach.stripe_id,
                            },
                        )

                        invoice = stripe.Invoice.pay(invoice.id)

                except Exception as e:
                    return Response({'error': 'An error occured during your purchase'})
            # # check if user has already subscribed to one of the coach's project
            # # Tier 1 subscribers have access to only 1 of the project so in this case we return error
            # if Team.objects.filter(project__coach=project.coach, members__in=[user.subscriber]).exists():
            #     return Response({'error': 'Tier 1 subscribers have access to only one project'})

        # This algorithm is not optimal and should be fixed in the future
        # Currently there is no equal distribution of members across teams
        # meaning that all teams will first become full sequentially and then new teams will be created
        # Instead an average should be calculated based on the amount of members that have joined the project
        # average = (total_members_joined / project.team_size). The algorithm should aim to populate teams
        # until "average" is reached and once that is reached populate other teams. That should reduce the
        # team size gap between teams

        # invoice needs to be populated regardless if the project was free or not
        if invoice['status'] == 'paid':
            team_found = False

            # First try to find a team with empty spots that has not started yet and add the user there
            for team in project.teams.all():
                has_started_progressing = team.milestone_completion_reports.count() > 0
                if team.members.count() < project.team_size and not has_started_progressing:
                    team_found = True
                    team.members.add(user.subscriber)

                    # add the user to all available chat rooms for this project
                    chat_rooms = ChatRoom.objects.filter(
                        project=project, team=team)
                    for chat_room in chat_rooms:
                        chat_room.members.add(user.subscriber)

                    return Response({'team': serializers.TeamSerializer(
                        team,
                        context={'request': request,
                                 'project': project}).data})

            # If no empty teams are found / or created create a new team only with this member
            if not team_found:
                new_team = Team.objects.create(
                    project=project, name=user.subscriber.name)
                new_team.members.add(user.subscriber)

                # create a new chat room for the team
                chat_room = ChatRoom.objects.create(name=user.subscriber.name, team=new_team,
                                                    team_type=ChatRoom.TEAM, project=project)
                chat_room.members.add(user.subscriber)

                # also create another chat room for the team + the coach
                chat_room_with_coach = ChatRoom.objects.create(team=new_team,
                                                               name=user.subscriber.name, team_type=ChatRoom.TEAM_WITH_COACH, project=project)
                chat_room_with_coach.members.add(
                    user.subscriber, project.coach.user.subscriber)

                return Response({'team': serializers.TeamSerializer(
                    new_team,
                    context={'request': request,
                             'project': project}).data})
        return Response({'error': 'An error occured during your purchase'})


@api_view(http_method_names=['POST', 'DELETE'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def create_stripe_subscription(request, id):
    user = request.user
    tier = Tier.objects.get(surrogate=id)
    creation_id = str(uuid.uuid4())
    ephemeralKey = stripe.EphemeralKey.create(
        customer=request.user.subscriber.customer_id,
        stripe_version='2020-08-27',
    )

    if request.method == 'POST':

        # First check if the user has already subscribed to this coach with another tier
        # if that is the case delete the existing one and initiate another subscription
        if Subscription.objects.filter(subscriber=user.subscriber, tier__coach=tier.coach).exists():
            sub_instance = Subscription.objects.filter(
                subscriber=user.subscriber, tier__coach=tier.coach).first()
            if tier.tier == Tier.FREE:
                # we don't handle free tiers on stripe
                # so just cancel the existing one on stripe and continue with the troosh free flow
                if sub_instance.subscription_id:
                    stripe.Subscription.delete(sub_instance.subscription_id)
                    sub_instance.subscription_id = None
                    sub_instance.json_data = None
                    sub_instance.tier = tier
                    sub_instance.price_id = None
                    sub_instance.save()
                    return Response({
                        'tier': tier.surrogate,
                        'creationId': creation_id
                    })
            else:
                subscription = stripe.Subscription.create(
                    customer=request.user.subscriber.customer_id,
                    items=[{
                        'price': tier.price_id,
                    }],
                    payment_behavior='default_incomplete',
                    default_source=None,
                    expand=['latest_invoice.payment_intent'],
                    application_fee_percent=20,
                    metadata={
                        'subscriber': request.user.subscriber.surrogate,
                        'tier': tier.surrogate,
                        'creation_id': creation_id,
                        'troosh_status': 'created',
                    },
                    transfer_data={
                        "destination": tier.coach.stripe_id,
                    },
                )
                # update the subscription on our end as well
                # sub_instance.subscription_id = subscription.id
                # sub_instance.json_data = json.dumps(subscription)
                # sub_instance.tier = tier
                # sub_instance.price_id = tier.price_id
                # sub_instance.save()
                return Response({
                    'subscriptionId': subscription.id,
                    'clientSecret': subscription.latest_invoice.payment_intent.client_secret,
                    'creationId': creation_id
                })
            # subscription = stripe.Subscription.retrieve(
            #     sub_instance.subscription_id)

            # subscription = stripe.Subscription.modify(
            #     subscription.id,
            #     cancel_at_period_end=False,
            #     proration_behavior='create_prorations',
            #     items=[{
            #         'id': subscription['items']['data'][0].id,
            #         'price': tier.price_id,
            #     }],
            #     metadata={
            #         'subscriber': request.user.subscriber.surrogate,
            #         'tier': tier.surrogate,
            #         'creation_id': creation_id,
            #         'troosh_status': 'updated',
            #     },

            #     expand=["latest_invoice.payment_intent"],
            #     application_fee_percent=20,
            #     transfer_data={
            #         "destination": tier.coach.stripe_id,
            #     }
            # )

            # update the subscription on our end as well
            # sub_instance.subscription_id = subscription.id,
            # sub_instance.json_data = json.dumps(subscription)
            # sub_instance.tier = tier
            # sub_instance.price_id = tier.price_id
            # sub_instance.save()

        # Then check if the user has already subscribed with the existing tier and return the tier
        # this will be a result of a possible bug so we don't need to do anything just return the existing tier
        if Subscription.objects.filter(subscriber=user.subscriber, tier=tier).exists():
            return Response({'tier': tier.surrogate})

        # If neither of the above scenarios happen create a completely new subscription
        if tier.tier == Tier.FREE:
            created_subscription = Subscription.objects.create(subscriber=user.subscriber, tier=tier,
                                                               customer_id=user.subscriber.customer_id)
            send_notification_on_subscribe(
                user.subscriber, tier, created_subscription)
            return Response({'tier': tier.surrogate})
        else:
            # If the tier is not free create a subcription instance
            subscription = stripe.Subscription.create(
                customer=request.user.subscriber.customer_id,
                items=[{
                    'price': tier.price_id,
                }],
                payment_behavior='default_incomplete',
                default_source=None,
                expand=['latest_invoice.payment_intent'],
                application_fee_percent=20,
                metadata={
                    'subscriber': request.user.subscriber.surrogate,
                    'tier': tier.surrogate,
                    'creation_id': creation_id,
                    'troosh_status': 'created',
                },
                transfer_data={
                    "destination": tier.coach.stripe_id,
                },
            )

            return Response({
                'subscriptionId': subscription.id,
                'clientSecret': subscription.latest_invoice.payment_intent.client_secret,
                'paymentIntentId': subscription.latest_invoice.payment_intent.id,
                'ephemeralKey': ephemeralKey.secret,
                'customer': request.user.subscriber.customer_id,
                'creationId': creation_id,
            })

        # If user is choosing any of the premium subcriptions (only tier 1 for now) create a coupon for a free project on the specific coach
        # if tier.tier != tier.FREE:
        #     coupon = None
        #     # Also create a coupon if it doesn't exist
        #     if not Coupon.objects.filter(subscriber=user.subscriber, coach=tier.coach).exists():
        #         coupon = stripe.Coupon.create(
        #             percent_off=100,
        #             duration="once",
        #         )

        #     created_subscription = Subscription.objects.create(subscriber=request.user.subscriber, subscription_id=subscription.id,
        #                                 customer_id=request.user.subscriber.customer_id, json_data=json.dumps(
        #                                     subscription),
        #                                 tier=tier, price_id=tier.price_id)

        #     if coupon:
        #         Coupon.objects.create(coach=tier.coach, subscriber=user.subscriber,
        #         coupon_id=coupon.id, valid=coupon.valid, json_data=json.dumps(coupon))

        # else:
        #     created_subscription = Subscription.objects.create(subscriber=request.user.subscriber, subscription_id=subscription.id,
        #                     customer_id=request.user.subscriber.customer_id, json_data=json.dumps(
        #                         subscription),
        #                     tier=tier, price_id=tier.price_id)

        # Also send coach notification about new subscriber
        # send_notification_on_subscribe(user.subscriber, tier, created_subscription)
    return Response({'error': 'Unexpected error occurred'})


@api_view(http_method_names=['POST'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def cancel_subscription(request, id):
    user = request.user
    tier = Tier.objects.get(surrogate=id)
    subcription = Subscription.objects.filter(subscriber=request.user.subscriber,
                                              tier=tier).first()
    subcription.delete()

    # remember to remove user from all his teams with this coach
    teams = Team.objects.filter(
        project__coach=tier.coach, members=user.subscriber)

    for team in teams:
        # remove user from all the relevant chat rooms for this project
        chat_rooms = ChatRoom.objects.filter(team=team)
        for chat_room in chat_rooms:
            chat_room.members.remove(user.subscriber)

        # remove subscriber from team
        team.members.remove(user.subscriber)

    # in case of free tier there is no subscription_id
    if subcription.subscription_id:
        stripe.Subscription.delete(subcription.subscription_id)
    return Response({'status': 'Successfully unsubscribed'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def preview_subscription_invoice(request, id):
    ephemeralKey = stripe.EphemeralKey.create(
        customer=request.user.subscriber.customer_id,
        stripe_version='2020-08-27',
    )

    # Retrieve the subscription
    subscription = stripe.Subscription.retrieve(id)

    # Retrive the Invoice
    invoice = stripe.Invoice.upcoming(
        customer=request.user.subscriber.customer_id,
        subscription=id,
        subscription_items=[{
            'id': subscription['items']['data'][0].id,
        }],
    )
    return Response({
        'payment_intent': invoice.payment_intent.client_secret,
        'ephemeral_key': ephemeralKey.secret,
        'customer': request.user.subscriber.customer_id
    })
    # return jsonify(invoice=invoice)


@api_view(http_method_names=['GET'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def card_wallet(request):
    setup_intent = stripe.SetupIntent.create(
        customer=request.user.subscriber.customer_id
    )
    client_secret = setup_intent.client_secret
    return Response({
        'clientSecret': client_secret,
    })


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def check_payment_intent_status(request, id):
    # Retrieve the Invoice
    # invoice = stripe.Invoice.retrieve(id)
    payment_intent = stripe.PaymentIntent.retrieve(id)
    return Response({
        'status': payment_intent.metadata.get('troosh_status')
    })


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def check_subscription_status(request, id):
    subscription = stripe.Subscription.retrieve(id)
    return Response({
        'status': subscription.metadata.get('troosh_status')
    })


@api_view(http_method_names=['POST', 'DELETE'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def subscribe(request, id):
    user = request.user
    tier = Tier.objects.get(surrogate=id)
    if request.method == 'POST':

        # First check if the user has already subscribed to this coach with another tier
        # if that is the case delete the existing one and initiate another subscription
        if Subscription.objects.filter(subscriber=user.subscriber, tier__coach=tier.coach).exists():
            sub_instance = Subscription.objects.filter(
                subscriber=user.subscriber, tier__coach=tier.coach).first()

            subscription = stripe.Subscription.retrieve(
                sub_instance.subscription_id)

            subscription = stripe.Subscription.modify(
                subscription.id,
                cancel_at_period_end=False,
                proration_behavior='create_prorations',
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': tier.price_id,
                }],
                expand=["latest_invoice.payment_intent"],
                application_fee_percent=20,
                transfer_data={
                    "destination": tier.coach.stripe_id,
                }
            )

            sub_instance.tier = tier
            sub_instance.json_data = json.dumps(subscription)
            sub_instance.subscription_id = subscription.id
            sub_instance.save()

            return Response({'tier': tier.surrogate})

        # Then check if the user has already subscribed with the existing tier and return the tier
        # this will be a result of a possible bug so we don't need to do anything just return the existing tier
        if Subscription.objects.filter(subscriber=user.subscriber, tier=tier).exists():
            return Response({'tier': tier.surrogate})

        # If neither of the above scenarios happen create a new subscription on both our end
        # and stripe
        subscription = stripe.Subscription.create(
            customer=request.user.subscriber.customer_id,
            items=[{
                'price': tier.price_id,
            }],
            application_fee_percent=20,
            transfer_data={
                "destination": tier.coach.stripe_id,
            },
        )

        # If user is choosing any of the premium subcriptions (only tier 1 for now) create a coupon for a free project on the specific coach
        if tier.tier != tier.FREE:
            coupon = None
            # Also create a coupon if it doesn't exist
            if not Coupon.objects.filter(subscriber=user.subscriber, coach=tier.coach).exists():
                coupon = stripe.Coupon.create(
                    percent_off=100,
                    duration="once",
                )

            created_subscription = Subscription.objects.create(subscriber=request.user.subscriber, subscription_id=subscription.id,
                                                               customer_id=request.user.subscriber.customer_id, json_data=json.dumps(
                                                                   subscription),
                                                               tier=tier, price_id=tier.price_id)

            if coupon:
                Coupon.objects.create(coach=tier.coach, subscriber=user.subscriber,
                                      coupon_id=coupon.id, valid=coupon.valid, json_data=json.dumps(coupon))

        else:
            created_subscription = Subscription.objects.create(subscriber=request.user.subscriber, subscription_id=subscription.id,
                                                               customer_id=request.user.subscriber.customer_id, json_data=json.dumps(
                                                                   subscription),
                                                               tier=tier, price_id=tier.price_id)

        # Also send coach notification about new subscriber
        send_notification_on_subscribe(
            user.subscriber, tier, created_subscription)
        # tier.subscribers.add(user)
    if request.method == 'DELETE':
        subcription = Subscription.objects.filter(subscriber=request.user.subscriber,
                                                  tier=tier).first()
        subcription.delete()

        # remember to remove user from all his teams with this coach
        teams = Team.objects.filter(
            project__coach=tier.coach, members=user.subscriber)

        for team in teams:
            # remove user from all the relevant chat rooms for this project
            chat_rooms = ChatRoom.objects.filter(team=team)
            for chat_room in chat_rooms:
                chat_room.members.remove(user.subscriber)

            # remove subscriber from team
            team.members.remove(user.subscriber)

        stripe.Subscription.delete(subcription.subscription_id)

    return Response({'tier': tier.surrogate})


@api_view(http_method_names=['POST', 'DELETE'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def attach_payment_method(request):
    user = request.user
    if request.method == 'POST':
        customer_id = request.user.subscriber.customer_id

        # attach the payment method to the customer
        payment_method = stripe.PaymentMethod.attach(
            request.data['id'],
            customer=customer_id,
        )

        # then modify the customer object to use the above payment method as the default
        stripe.Customer.modify(
            request.user.subscriber.customer_id,
            invoice_settings={"default_payment_method": payment_method.id},
        )
        return Response({'payment_id': payment_method.id})
    if request.method == 'DELETE':
        return Response({'payment_id': None})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_payment_method(request):
    user = request.user
    customer_id = request.user.subscriber.customer_id

    customer = stripe.Customer.retrieve(customer_id)

    payment_method_id = customer['invoice_settings']['default_payment_method']
    if payment_method_id:
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        return Response({'payment_method': {
            'id': payment_method['id'],
            'card': {
                'last4': payment_method['card']['last4']
            },
        }})
    return Response({'payment_method': None})


@api_view(http_method_names=['PUT', 'DELETE'])
@permission_classes((permissions.IsAuthenticated,))
def change_or_delete_react(request, id):
    user = request.user
    post = Post.objects.get(surrogate=id)
    react = post.reacts.filter(user=user).first()
    if request.method == 'PUT':
        if not react:
            react = post.reacts.create(user=user)
    if request.method == 'DELETE':
        if react:
            post.reacts.remove(react)
    react_count = post.reacts.count()
    return Response({'react_count': react_count})


@api_view(http_method_names=['PUT', 'DELETE'])
@permission_classes((permissions.IsAuthenticated,))
def change_or_delete_comment_react(request, id):
    user = request.user
    comment = Comment.objects.get(surrogate=id)
    react = comment.reacts.filter(user=user).first()
    if request.method == 'PUT':
        if not react:
            react = comment.reacts.create(user=user)
    if request.method == 'DELETE':
        if react:
            comment.reacts.remove(react)
    react_count = comment.reacts.count()
    return Response({'react_count': react_count})


@api_view(http_method_names=['PATCH'])
@permission_classes((permissions.IsAuthenticated,))
def update_milestone_report_from_task_id(request, milestone_report_id):
    user = request.user
    milestone_report = MilestoneCompletionReport.objects.get(
        surrogate=milestone_report_id)

    if user.coach and milestone_report.milestone.project.coach == user.coach:
        serializer = serializers.CoachUpdateMilestoneCompletionReportSerializer(
            milestone_report, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    else:
        # TODO
        # create another SubscriberUpdateMilestoneSerializer for subscribers to edit their report
        pass

    return Response({'error': 'An unexpected error has occured'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def select_expertise(request):
    user = request.user
    if user.coach:
        # ideally we would set this in the if block below
        # but it's important for the user to not get stuck on the "select expertise screen"
        # so we accept soft errors
        user.coach.submitted_expertise = True
        if request.data['expertise']:
            expertise_field = ExpertiseField.objects.filter(
                name=request.data['expertise'])
            if expertise_field.exists():
                expertise_field = expertise_field.first()
                user.coach.expertise_field = expertise_field
            else:
                # Can safely populate this, we later see results in the admin panel
                ExpertiseFieldSuggestion.objects.create(
                    name=request.data['expertise'], suggested_by=user.coach)
        user.coach.save()

    return Response({'error': 'An unexpected error has occured'})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def upload_video(request):
    # Authentication Setup
    configuration = mux_python.Configuration()
    configuration.username = os.environ['MUX_TOKEN_ID']
    configuration.password = os.environ['MUX_TOKEN_SECRET']

    passthrough_id = str(uuid.uuid1())

    # Mark post as processing while video is being processed by mux
    post = Post.objects.get(surrogate=request.data['post'])
    post.status == Post.PROCESSING
    post.save(processing=True)
    PostVideoAssetMetaData.objects.create(
        passthrough=passthrough_id, post=post)
    create_asset_request = mux_python.CreateAssetRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
                                                         mp4_support="standard", passthrough=passthrough_id)

    # API Client Initialization
    request = mux_python.CreateUploadRequest(
        new_asset_settings=create_asset_request, test=True if settings.DEVELOPMENT_MODE else False)
    direct_uploads_api = mux_python.DirectUploadsApi(
        mux_python.ApiClient(configuration))
    response = direct_uploads_api.create_direct_upload(request)

    try:
        pass
    except ApiException as e:
        print("Exception when calling AssetsApi->list_assets: %s\n" % e)
    return Response({"url": response.data.url})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def upload_milestonecompletion_video(request):
    # Authentication Setup
    configuration = mux_python.Configuration()
    configuration.username = os.environ['MUX_TOKEN_ID']
    configuration.password = os.environ['MUX_TOKEN_SECRET']

    passthrough_id = str(uuid.uuid1())

    # Mark milestone report as processing while video is being processed by mux
    milestone_completion_report = MilestoneCompletionReport.objects.get(
        surrogate=request.data['milestone_completion_report'])
    milestone_completion_report.video_status == MilestoneCompletionReport.PROCESSING
    milestone_completion_report.save()
    MilestoneCompletionVideoAssetMetaData.objects.create(
        passthrough=passthrough_id, milestone_completion_report=milestone_completion_report)
    create_asset_request = mux_python.CreateAssetRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
                                                         mp4_support="standard", passthrough=passthrough_id)

    # API Client Initialization
    request = mux_python.CreateUploadRequest(
        new_asset_settings=create_asset_request, test=True if settings.DEVELOPMENT_MODE else False)
    direct_uploads_api = mux_python.DirectUploadsApi(
        mux_python.ApiClient(configuration))
    response = direct_uploads_api.create_direct_upload(request)

    try:
        pass
    except ApiException as e:
        print("Exception when calling AssetsApi->list_assets: %s\n" % e)
    return Response({"url": response.data.url})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def upload_video_webhook(request):
    if request.data['type'] == 'video.asset.ready':
        passthrough = request.data['data']['passthrough']
        playback_ids = request.data['data']['playback_ids']
        asset_id = request.data['data']['id']

        # in case the video is attached to a post
        if PostVideoAssetMetaData.objects.filter(passthrough=passthrough).exists():
            video_data = PostVideoAssetMetaData.objects.get(
                passthrough=passthrough)
            video = PostVideo.objects.create(
                asset_id=asset_id, passthrough=video_data.passthrough, post=video_data.post)
            for playback_id in playback_ids:
                PlaybackId.objects.create(
                    playback_id=playback_id['id'], policy=playback_id['policy'], video=video)
            # Video is done processing by mux. Mark it as done.
            video_data.post.status = Post.DONE
            video_data.post.save()

        # in case the video is attached to a post
        if MilestoneCompletionVideoAssetMetaData.objects.filter(passthrough=passthrough).exists():
            video_data = MilestoneCompletionVideoAssetMetaData.objects.get(
                passthrough=passthrough)
            video = MilestoneCompletionVideo.objects.create(
                asset_id=asset_id, passthrough=video_data.passthrough, milestone_completion_report=video_data.milestone_completion_report)
            for playback_id in playback_ids:
                MilestoneCompletionPlaybackId.objects.create(
                    playback_id=playback_id['id'], policy=playback_id['policy'], video=video)
            # Video is done processing by mux. Mark it as done.
            video_data.milestone_completion_report.status = MilestoneCompletionReport.DONE
            video_data.milestone_completion_report.save()
    return Response()


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_stripe_login(request):
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    login = stripe.Account.create_login_link(f'{request.user.coach.stripe_id}')
    return Response({'url': login.url})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def create_stripe_account_link(request):
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    coach = request.user.coach

    redirect = 'https://troosh.app/users/oauth/callback'
    refresh_url = 'https://troosh.app/reauth'

    account_link = stripe.AccountLink.create(
        account=request.user.coach.stripe_id,
        refresh_url=refresh_url,
        return_url=redirect,
        type="account_onboarding",
    )

    coach.stripe_account_link = account_link.url
    coach.stripe_created = account_link.created
    coach.stripe_expires_at = account_link.expires_at
    coach.save()
    return Response({'url': account_link.url})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def create_stripe_account_link_qa(request):
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    coach = request.user.coach

    redirect = 'https://questions.troosh.app/users/oauth/callback'
    refresh_url = 'https://questions.troosh.app/reauth'

    account_link = stripe.AccountLink.create(
        account=request.user.coach.stripe_id,
        refresh_url=refresh_url,
        return_url=redirect,
        type="account_onboarding",
    )

    coach.stripe_account_link = account_link.url
    coach.stripe_created = account_link.created
    coach.stripe_expires_at = account_link.expires_at
    coach.save()
    return Response({'url': account_link.url})


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_stripe_balance(request):
    balance = stripe.Balance.retrieve(
        stripe_account=request.user.coach.stripe_id
    )
    print(balance)
    return Response({
        'available': balance['available'][0]['amount'] / 100,
        'pending':  balance['pending'][0]['amount'] / 100
    })


@csrf_exempt
@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    # endpoints received from "account" and "connect applications" both land here
    # so we have to check both signatured
    # if one fails try the other
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_ENDPOINT_SECRET')
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, os.environ.get(
                    'STRIPE_ENDPOINT_REGULAR_SECRET')
            )
        except stripe.error.SignatureVerificationError as e2:
            # Invalid signature
            return HttpResponse(status=400)

    data_object = event.data.object
    if event.type == 'payment_intent.payment_failed':
        payment_intent_id = data_object['id']
        stripe.PaymentIntent.modify(
            payment_intent_id,
            metadata={
                'troosh_status': 'payment_failed'
            }
        )

    if event.type == 'payment_intent.succeeded':
        payment_intent_id = data_object['id']
        payment_intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
        )
        payment_type = payment_intent.metadata.get('type')
        if payment_type == 'project':
            project_id = payment_intent.metadata['id']
            subscriber = payment_intent.metadata['subscriber']
            subscriber = Subscriber.objects.filter(
                surrogate=subscriber).first()
            project = Project.objects.filter(surrogate=project_id).first()
            if project:
                handle_join_project(project, subscriber)
                stripe.PaymentIntent.modify(
                    payment_intent_id,
                    metadata={
                        'troosh_status': 'completed'
                    }
                )
                return Response({'success': 'Successfully joined project'})
            else:
                return Response({'error': f"Project with id {project_id} not found"})

        # return Response({'error': json.dumps(payment_intent)})

    if event.type == 'checkout.session.completed':
        checkout_session = stripe.checkout.Session.retrieve(
            data_object['id'],
            expand=['customer']
        )
        # get customer so we can send him an email with the zoom link
        customer = checkout_session['customer']
        qa_session = QaSession.objects.get(
            surrogate=data_object.metadata['id'])
        question = Question.objects.get(
            surrogate=data_object.metadata['question_id'])
        zoom_end_time = question.initial_delivery_time + \
            datetime.timedelta(minutes=int(qa_session.minutes))
        question.delivery_time = zoom_end_time
        question.delivered_by = qa_session.coach
        question.save()
        zoom_meeting_data = create_meeting(
            question.initial_delivery_time, qa_session.minutes, qa_session.coach)

        # also save zoom data in admin
        question.zoom_link = zoom_meeting_data['url']
        question.zoom_password = zoom_meeting_data['password']
        question.save()

        # send email to the customer
        send_mail(
            f"Your zoom call with {qa_session.coach.name}",
            f"""
            Here is your zoom meeting:

            Start time: {zoom_meeting_data['start_time'].strftime("%m/%d/%Y, %H:%M:%S")} UTC
            Duration: {qa_session.minutes}
            Link: {zoom_meeting_data['url']}
            Password: {zoom_meeting_data['password']}
            
            For any questions feel free to reply to this email!
            """,
            'beta@troosh.app',
            [customer['email']],
            fail_silently=False,
        )

        # send email to mentor
        send_mail(
            f"You got a zoom call coming up!",
            f"""
            Here is your zoom meeting for the following question: 
            "{question.body}"
            
            Start time: {zoom_meeting_data['start_time'].strftime("%m/%d/%Y, %H:%M:%S")} UTC
            Duration: {qa_session.minutes}
            Link: {zoom_meeting_data['url']}
            Password: {zoom_meeting_data['password']}
            
            For any questions feel free to reply to this email!
            """,
            'beta@troosh.app',
            [qa_session.coach.user.email],
            fail_silently=False,
        )

        return Response({'url': zoom_meeting_data['url'], 'password': zoom_meeting_data['password']})

    if event.type == 'invoice.payment_failed':
        if data_object['billing_reason'] == 'subscription_create' or data_object['billing_reason'] == 'subscription_update':
            subscription_id = data_object['subscription']
            payment_intent_id = data_object['payment_intent']

            # Retrieve the payment intent used to pay the subscription
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            subscription = stripe.Subscription.modify(
                subscription_id,
                # default_payment_method=payment_intent.payment_method,
                metadata={
                    'troosh_status': 'payment_failed'
                }
            )

    if event.type == 'invoice.payment_succeeded':
        if data_object['billing_reason'] == 'subscription_create' or data_object['billing_reason'] == 'subscription_update':
            # The subscription automatically activates after successful payment
            # Set the payment method used to pay the first invoice
            # as the default payment method for that subscription
            subscription_id = data_object['subscription']
            payment_intent_id = data_object['payment_intent']

            # Retrieve the payment intent used to pay the subscription
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            subscription = stripe.Subscription.retrieve(subscription_id)
            sub_instance = Subscription.objects.filter(
                subscription_id=subscription_id)
            subscriber = subscription.metadata['subscriber']
            tier = subscription.metadata['tier']
            subscriber = Subscriber.objects.filter(
                surrogate=subscriber).first()
            tier = Tier.objects.filter(surrogate=tier).first()

            existing_subscription = Subscription.objects.filter(
                subscriber=subscriber, tier__coach=tier.coach)
            if existing_subscription.exists():
                existing_subscription = existing_subscription.first()
                existing_subscription.subscription_id = subscription.id
                existing_subscription.json_data = json.dumps(subscription)
                existing_subscription.tier = tier
                existing_subscription.price_id = tier.price_id
                existing_subscription.save()
            else:
                created_subscription = Subscription.objects.create(subscriber=subscriber, subscription_id=subscription.id,
                                                                   customer_id=subscriber.customer_id, json_data=json.dumps(
                                                                       subscription),
                                                                   tier=tier, price_id=tier.price_id)
                send_notification_on_subscribe(
                    subscriber, tier, created_subscription)

            if tier.tier != Tier.FREE:
                coupon = None
                if not Coupon.objects.filter(subscriber=subscriber, coach=tier.coach).exists():
                    coupon = stripe.Coupon.create(
                        percent_off=100,
                        duration="once",
                    )
                if coupon:
                    Coupon.objects.create(coach=tier.coach, subscriber=subscriber,
                                          coupon_id=coupon.id, valid=coupon.valid, json_data=json.dumps(coupon))

            # Update the status of the subscription
            # Set the default payment method
            subscription = stripe.Subscription.modify(
                subscription_id,
                # default_payment_method=payment_intent.payment_method,
                metadata={
                    'troosh_status': 'completed'
                }
            )

    if event.type == 'payment_method.attached':
        payment_method = event.data.object  # contains a stripe.PaymentMethod
    elif event.type == 'account.updated':
        charges_enabled = data_object.get('charges_enabled', '')
        coach = Coach.objects.get(stripe_id=data_object.get('id', ''))
        coach.charges_enabled = charges_enabled
        coach.save()
    else:
        print('Unhandled event type {}'.format(event.type))
    return HttpResponse(status=200)
