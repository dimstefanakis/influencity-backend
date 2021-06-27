import os
from collections import OrderedDict
import mux_python
from mux_python.rest import ApiException
from django.contrib.sites.models import Site
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
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
from . import serializers
import uuid
import stripe
import json
import channels.layers
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


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

class UserMeViewSet(mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.UserMeSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        # UserMeNoCoachSerializer
        user = self.get_queryset()
        print(user.first().is_coach)
        if user.first().is_coach:
            return serializers.UserMeSerializer
        return serializers.UserMeNoCoachSerializer

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)

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
        if self.action=='list' or self.action=='retrieve':
            queryset = Coach.objects.filter(charges_enabled=True)
        else:
            queryset = Coach.objects.all()

        username = self.request.query_params.get('username', None)
        return queryset

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


class PostViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = Post.objects.all()
    serializer_class = serializers.PostSerializer
    lookup_field = 'surrogate'

    def get_serializer_class(self):
        if self.action == 'create':
            print(self.request.data)
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
        subscription = Subscription.objects.filter(subscriber=self.request.user.subscriber, tier__coach=coach).first()
        # by default get all posts available (except the ones that are chained to others, in that case just get the initial), 
        # later we exclude posts based on the user subscription
        post_query |= coach.posts.exclude(parent_post__isnull=False)
            
        if subscription:
            # if use has subscriberd to tier 1 exclude tier 2 posts
            if subscription.tier.tier==Tier.TIER1:
                post_query = post_query.exclude(coach=coach, tier__tier=Tier.TIER2)
            elif subscription.tier.tier==Tier.FREE:
                post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])
        else:
            # if the user is the coach don't exclude anything
            if self.request.user != coach.user:
                post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])

        return post_query.distinct()


class ChainedPostsViewSet(generics.ListCreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainedPostsSerializer


class NewPostsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.PostSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        post_query = Post.objects.none()
        for coach in Coach.objects.filter(tiers__subscriptions__subscriber=self.request.user.subscriber).exclude(user=self.request.user):
            subscription = Subscription.objects.filter(subscriber=self.request.user.subscriber, tier__coach=coach).first()
            # by default get all posts available (except the ones that are chained to others, in that case just get the initial), 
            # later we exclude posts based on the user subscription
            post_query |= coach.posts.exclude(parent_post__isnull=False)
                
            # if use has subscriberd to tier 1 exclude tier 2 posts
            if subscription.tier.tier==Tier.TIER1:
                post_query = post_query.exclude(coach=coach, tier__tier=Tier.TIER2)
            elif subscription.tier.tier==Tier.FREE:
                post_query = post_query.exclude(coach=coach, tier__tier__in=[Tier.TIER2, Tier.TIER1])

        # user might not be a coach, in that case an exception is thrown
        try:
            post_query = post_query | Post.objects.filter(coach=self.request.user.coach).exclude(parent_post__isnull=False)
        except Exception:
            pass
        return post_query.distinct()

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
    permission_classes = [permissions.IsAuthenticated, ]
    lookup_field = 'surrogate'

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update' or self.action == 'partial_update':
            return serializers.CreateOrUpdateProjectSerializer
        return serializers.ProjectSerializer

    def get_serializer_context(self):
        return {
            'request': self.request,
        }
    # def get_permissions(self):
    #     """
    #     Instantiates and returns the list of permissions that this view requires.
    #     """
    #     if self.action == 'create':
    #         permission_classes = [permissions.IsAuthenticated]
    #     else:
    #         permission_classes = [permissions.IsAuthenticated]
    #     return [permission() for permission in permission_classes]


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
        if self.request.user.coach:
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
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,]

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
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,]

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyAwardsViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = serializers.AwardSerializer
    permission_classes = [permissions.IsAuthenticated,]

    def get_queryset(self):
        subscriber = self.request.user.subscriber
        return subscriber.awards.all()


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


@api_view(http_method_names=['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_unread_count(request):
    return Response({'unread_count': request.user.notifications.unread().count()})


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def mark_all_read(request):
    request.user.notifications.mark_all_as_read()
    return Response({'unread_count': request.user.notifications.unread().count()})


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
        serializer = serializers.CoachSerializer(coach, context={'request':request})
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

        subscription = Subscription.objects.filter(subscriber=user.subscriber, tier__coach=project.coach)
        if not subscription.exists():
            return Response({'error': 'You need to be at least Tier 1 subsciber or above to join projects'})
        subscription = subscription.first()
        if subscription.tier.tier == Tier.FREE:
            return Response({'error': 'Free tier subscribers cannot join projects'})
        elif subscription.tier.tier == Tier.TIER1:
            invoice = None
            payment_intent = None
            coupon = Coupon.objects.filter(subscriber=request.user.subscriber, coach=project.coach)
            if coupon.exists():
                coupon = coupon.first()
                price = stripe.Price.retrieve(
                    project.price_id,
                )
                if coupon.valid:
                    # 100% discount is applied here, no need for stripe to do anything
                    handle_join_project(project, request.user.subscriber, request)
                    coupon.valid = False
                    coupon.save()
                else:
                    payment_intent = stripe.PaymentIntent.create(
                        amount=price.unit_amount,
                        currency="usd",
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
        subscription = Subscription.objects.filter(subscriber=user.subscriber, tier__coach=project.coach)
        if not subscription.exists():
            return Response({'error': 'You need to be at least Tier 1 subsciber or above to join projects'})
        subscription = subscription.first()
        if subscription.tier.tier == Tier.FREE:
            return Response({'error': 'Free tier subscribers cannot join projects'})
        elif subscription.tier.tier == Tier.TIER1:
            coupon = Coupon.objects.filter(subscriber=request.user.subscriber, coach=project.coach)

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
                            currency="usd",
                            #amount=price.unit_amount,
                            discounts=[{
                                'coupon': coupon.coupon_id,
                            }],
                        )

                        # using int rounds down
                        invoice = stripe.Invoice.create(
                            customer=request.user.subscriber.customer_id,
                            application_fee_amount=int(price.unit_amount * 0.2),
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
                            #amount=price.unit_amount,
                            currency="usd",
                        )

                        # using int rounds down
                        invoice = stripe.Invoice.create(
                            customer=request.user.subscriber.customer_id,
                            application_fee_amount=int(price.unit_amount * 0.2),
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


def send_notification_on_subscribe(subscriber, tier, subscription):
    channel_layer = channels.layers.get_channel_layer()
    notification_data = notify.send(subscriber, recipient=tier.coach.user, verb=f'Just subscribed on your {tier.label.lower()} tier!', action_object=subscription)

    notification = notification_data[0][1][0]
    async_to_sync(channel_layer.group_send)(
        f"{str(tier.coach.user.surrogate)}.notifications.group",
        {
            'type': 'send.notification',
            'id': notification.id
        }
    )

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
                metadata={
                    'subscriber': request.user.subscriber.surrogate,
                    'tier': tier.surrogate,
                    'creation_id': creation_id,
                    'troosh_status': 'updated',
                },

                expand=["latest_invoice.payment_intent"],
                application_fee_percent=20,
                transfer_data={
                    "destination": tier.coach.stripe_id,
                }           
            )

            return Response({
                'subscriptionId': subscription.id,
                'clientSecret': subscription.latest_invoice.payment_intent.client_secret,
                'creationId': creation_id
            })

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
            payment_behavior='default_incomplete',
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
        'customer': request.user.subscriber.costumer_id
    })
    #return jsonify(invoice=invoice)

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
        send_notification_on_subscribe(user.subscriber, tier, created_subscription)
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
            'card':{
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
    milestone_report = MilestoneCompletionReport.objects.get(surrogate=milestone_report_id)

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
            expertise_field = ExpertiseField.objects.filter(name=request.data['expertise'])
            if expertise_field.exists():
                expertise_field = expertise_field.first()
                user.coach.expertise_field = expertise_field
            else:
                # Can safely populate this, we later see results in the admin panel
                ExpertiseFieldSuggestion.objects.create(name=request.data['expertise'], suggested_by=user.coach)
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
        new_asset_settings=create_asset_request, test=True)
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
        new_asset_settings=create_asset_request, test=True)
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

    if settings.DEBUG:
        redirect = 'http://localhost:3000/users/oauth/callback'
        refresh_url = "http://localhost:3000/reauth"

    else:
        redirect = 'https://%s%s' % (Site.objects.get_current().domain,
                                     '/users/oauth/callback')
        refresh_url = 'https://%s%s' % (
            Site.objects.get_current().domain, '/reauth')

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
                payload, sig_header, os.environ.get('STRIPE_ENDPOINT_REGULAR_SECRET')
            )
        except stripe.error.SignatureVerificationError as e2:
            # Invalid signature
            return HttpResponse(status=400)

    data_object = event.data.object
    if event.type == 'payment_intent.succeeded':
        payment_intent_id = data_object['id']
        payment_intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
        )
        payment_type = payment_intent.metadata.get('type')
        if payment_type == 'project':
            project_id = payment_intent.metadata['id']
            subscriber = payment_intent.metadata['subscriber']
            subscriber = Subscriber.objects.filter(surrogate=subscriber).first()
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
        return Response({'error': json.dumps(payment_intent)})

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
            sub_instance = Subscription.objects.filter(subscription_id=subscription_id)
            subscriber = subscription.metadata['subscriber']
            tier = subscription.metadata['tier']
            subscriber = Subscriber.objects.filter(surrogate=subscriber).first()
            tier = Tier.objects.filter(surrogate=tier).first()

            if not sub_instance.exists():
                coupon = None
                created_subscription = Subscription.objects.create(subscriber=subscriber, subscription_id=subscription.id,
                                        customer_id=subscriber.customer_id, json_data=json.dumps(subscription),
                                        tier=tier, price_id=tier.price_id)
                if not Coupon.objects.filter(subscriber=subscriber, coach=tier.coach).exists():
                    coupon = stripe.Coupon.create(
                        percent_off=100,
                        duration="once",
                    )
                if coupon:
                    Coupon.objects.create(coach=tier.coach, subscriber=subscriber,
                    coupon_id=coupon.id, valid=coupon.valid, json_data=json.dumps(coupon))

            else:
                created_subscription = Subscription.objects.create(subscriber=subscriber, subscription_id=subscription.id,
                customer_id=subscriber.customer_id, json_data=json.dumps(
                    subscription),
                tier=tier, price_id=tier.price_id)

            # Update the status of the subscription
            # Set the default payment method
            subscription = stripe.Subscription.modify(
                subscription_id,
                default_payment_method=payment_intent.payment_method,
                metadata={
                    'troosh_status': 'completed'
                }
            )

            send_notification_on_subscribe(subscriber, tier, created_subscription)


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
