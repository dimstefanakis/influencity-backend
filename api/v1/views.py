import os
import mux_python
from mux_python.rest import ApiException
from rest_framework import viewsets, mixins, permissions, generics
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters import rest_framework as filters
from accounts.models import User
from instructor.models import Coach
from posts.models import Post, PostVideoAssetMetaData, PostVideo
from projects.models import Project, Team
from expertisefields.models import ExpertiseField
from tiers.models import Tier
from . import serializers
import uuid

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class UserMeViewSet(mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)


class CoachFilterSet(filters.FilterSet):
    expertise = filters.CharFilter(field_name="expertise_field__name", lookup_expr="iexact")
    expertise_field = filters.ModelChoiceFilter(queryset=ExpertiseField.objects.all())

    class Meta:
        model = Coach
        fields = ['expertise_field', 'expertise']


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


class MyCoachesViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.CoachSerializer

    def get_queryset(self):
        if self.request.user.coach:
            return self.request.user.coaches.exclude(user=self.request.user)
        return self.request.user.coaches.all()


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.PostSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.PostCreateSerializer
        return serializers.PostSerializer

    def get_queryset(self):
        # prevents chained posts from being displayed outside parent post
        return Post.objects.exclude(parent_post__isnull=False)


class ChainedPostsViewSet(generics.ListCreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainedPostsSerializer


class NewPostsViewSet(viewsets.ModelViewSet):

    serializer_class = serializers.CoachNewPosts

    def get_queryset(self):
        return self.request.user.coaches.all()


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
    serializer_class = serializers.TierSerializer

    def get_queryset(self):
        return self.request.user.coach.tiers.all()


class MyTeamsViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TeamSerializer

    def get_queryset(self):
        return self.request.user.subscriber.teams.all()


@api_view(http_method_names=['POST'])
@permission_classes((permissions.AllowAny,))
def upload_video(request):
    # Authentication Setup
    configuration = mux_python.Configuration()
    configuration.username = os.environ['MUX_TOKEN_ID']
    configuration.password = os.environ['MUX_TOKEN_SECRET']

    passthrough_id = str(uuid.uuid1())
    PostVideoAssetMetaData.objects.create(passthrough=passthrough_id, post=Post.objects.get(pk=request.data['post']))
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
        PostVideo.objects.create(asset_id=asset_id, passthrough=video_data.passthrough, post=video_data.post)
    return Response()
