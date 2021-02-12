import os
import mux_python
from mux_python.rest import ApiException
from rest_framework.views import APIView
from rest_framework import viewsets, mixins, permissions, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from rest_framework.decorators import parser_classes
from rest_framework.parsers import MultiPartParser, JSONParser
from django_filters import rest_framework as filters
from accounts.models import User
from subscribers.models import Subscriber, Subscription
from instructor.models import Coach, CoachApplication
from posts.models import Post, PostVideoAssetMetaData, PlaybackId, PostVideo
from projects.models import Project, Team, MilestoneCompletionReport, Milestone
from tiers.models import Tier
from expertisefields.models import ExpertiseField
from comments.models import Comment
from reacts.models import React
from chat.models import ChatRoom, Message
from . import serializers
import uuid
import stripe
import json
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


class MessagePagination(CursorPagination):
    page_size = 20
    max_page_size = 100


class CommentPagination(CursorPagination):
    page_size = 10
    max_page_size = 100


class PostPagination(CursorPagination):
    page_size = 15
    max_page_size = 30


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class UserMeViewSet(mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.UserMeSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        #UserMeNoCoachSerializer
        user = self.get_queryset()
        print(user.first().is_coach)
        if user.first().is_coach:
            return serializers.UserMeSerializer
        return serializers.UserMeNoCoachSerializer

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)


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
    expertise = filters.CharFilter(field_name="expertise_field__name", lookup_expr="iexact")
    expertise_field = filters.ModelChoiceFilter(queryset=ExpertiseField.objects.all())

    class Meta:
        model = Coach
        fields = ['expertise_field', 'expertise', 'name']


class CoachViewSet(viewsets.ModelViewSet):
    queryset = Coach.objects.all()
    serializer_class = serializers.CoachSerializer
    #filterset_fields = ['expertise_field']
    filterset_class = CoachFilterSet

    def get_queryset(self):
        """
        Optionally restricts the returned purchases to a given user,
        by filtering against a `username` query parameter in the URL.
        """
        queryset = Coach.objects.all()
        username = self.request.query_params.get('username', None)
        if username is not None:
            queryset = queryset.filter(purchaser__username=username)
        return queryset


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
            return self.request.user.coaches.exclude(user=self.request.user)
        return self.request.user.coaches.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class PostViewSet(viewsets.ModelViewSet):
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
        return Post.objects.filter(coach__surrogate=surrogate)


class ChainedPostsViewSet(generics.ListCreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainedPostsSerializer


class NewPostsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = serializers.PostSerializer
    pagination_class = PostPagination

    def get_queryset(self):
        post_query = Post.objects.none()
        for coach in self.request.user.coaches.all():
            post_query |= coach.posts.exclude(parent_post__isnull=False)
        return post_query

    def get_serializer_context(self):
        return {
            'request': self.request
        }


class ChainPostsViewSet(generics.CreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainPostsSerializer


class ProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer


class MyProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.MyProjectsSerializer

    def get_queryset(self):
        return self.request.user.subscriber.projects.all()

    def get_serializer_context(self):
        return {
            'request': self.request,
        }


class MyCreatedProjectsViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer

    def get_queryset(self):
        if self.request.user.coach:
            return self.request.user.coach.created_projects.all()
        else:
            return Project.objects.none()


class TeamsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TeamSerializer

    def get_queryset(self):
        project = self.kwargs['project_id']
        return Team.objects.filter(project=project)


class ExpertiseViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ExpertiseSerializer
    queryset = ExpertiseField.objects.all()


class MyTiersViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, ]

    def get_serializer_class(self):
        if self.action == 'update' or self.action=='partial_update':
            return serializers.UpdateTierSerializer
        else:
            return serializers.TierSerializer

    def get_queryset(self):
        if self.request.user.is_coach:
            return self.request.user.coach.tiers.all()
        else:
            return Tier.object.none()


class MyTeamsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TeamSerializer
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


class CreateCommentViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    serializer_class = serializers.CreateCommentSerializer
    pagination_class = CommentPagination
    queryset = Comment.objects.all()

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


class MilestoneCompletionReportViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.MilestoneCompletionReportSerializer
    queryset = MilestoneCompletionReport.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            print(self.request.data)
            return serializers.CreateMilestoneCompletionReportSerializer
        return serializers.MilestoneCompletionReportSerializer

    def get_queryset(self):
        milestone = Milestone.objects.filter(id=self.kwargs['milestone_id']).first()
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


@api_view(http_method_names=['GET', 'PATCH'])
@permission_classes((permissions.IsAuthenticated,))
def subscriber_me(request):
    user = request.user
    subscriber = Subscriber.objects.filter(user=user.pk).first()
    if request.method == 'GET':
        serializer = serializers.SubscriberSerializer(subscriber)
        return Response(serializers.SubscriberSerializer)
    elif request.method == 'PATCH':
        serializer = serializers.SubscriberUpdateSerializer(subscriber, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(http_method_names=['POST', 'DELETE'])
@parser_classes([JSONParser])
@permission_classes((permissions.IsAuthenticated,))
def subscribe(request, id):
    user = request.user
    tier = Tier.objects.get(surrogate=id)
    if request.method == 'POST':
        subscription = stripe.Subscription.create(
            customer=request.user.subscriber.customer_id,
            items=[{
                'price': tier.price_id,
            }],
        )

        Subscription.objects.create(subscriber=request.user.subscriber, subscription_id=subscription.id,
                                    customer_id=request.user.subscriber.customer_id, json_data=json.dumps(subscription),
                                    tier=tier)
        # tier.subscribers.add(user)
    if request.method == 'DELETE':
        subcription = Subscription.objects.filter(subscriber=request.user.subscriber,
                                   tier=tier).first()
        stripe.Subscription.delete(subcription.subscription_id)

        # tier.subscribers.remove(user)
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


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def upload_video(request):
    # Authentication Setup
    configuration = mux_python.Configuration()
    configuration.username = os.environ['MUX_TOKEN_ID']
    configuration.password = os.environ['MUX_TOKEN_SECRET']

    passthrough_id = str(uuid.uuid1())
    
    # Mark post as processing while video is being processed by mux
    post = Post.objects.get(pk=request.data['post'])
    post.status == Post.PROCESSING
    post.save()
    PostVideoAssetMetaData.objects.create(passthrough=passthrough_id, post=post)
    create_asset_request = mux_python.CreateAssetRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
                                                         mp4_support="standard", passthrough=passthrough_id)

    # API Client Initialization
    request = mux_python.CreateUploadRequest(new_asset_settings=create_asset_request, test=True)
    direct_uploads_api = mux_python.DirectUploadsApi(mux_python.ApiClient(configuration))
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
        video_data = PostVideoAssetMetaData.objects.get(passthrough=passthrough)
        video = PostVideo.objects.create(asset_id=asset_id, passthrough=video_data.passthrough, post=video_data.post)
        for playback_id in playback_ids:
            PlaybackId.objects.create(playback_id=playback_id['id'], policy=playback_id['policy'], video=video)
        # Video is done processing by mux. Mark it as done.
        video_data.post.status = Post.DONE
        video_data.post.save()
    return Response()


@api_view(http_method_names=['POST'])
@permission_classes((permissions.IsAuthenticated,))
def get_stripe_login(request):
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
    login = stripe.Account.create_login_link(f'{request.user.coach.stripe_id}')
    return Response({'url': login.url})
