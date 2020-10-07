from rest_framework import viewsets, mixins, permissions, generics
from accounts.models import User
from instructor.models import Coach
from posts.models import Post
from projects.models import Project
from . import serializers


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer


class UserMeViewSet(mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.UserSerializer
    permission_classes = [permissions.IsAuthenticated, ]

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)


class CoachViewSet(viewsets.ModelViewSet):
    queryset = Coach.objects.all()
    serializer_class = serializers.CoachSerializer


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.PostSerializer

    def get_serializer_class(self):
        if self.action == 'create':
            return serializers.PostCreateSerializer
        return serializers.PostSerializer


class ChainedPostsViewSet(generics.ListCreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainedPostsSerializer


class NewPostsViewSet(viewsets.ModelViewSet):

    serializer_class = serializers.NewPostsSerializer

    def get_queryset(self):
        return self.request.user.coaches.all()


class ChainPostsViewSet(generics.CreateAPIView, viewsets.GenericViewSet):
    queryset = Post.objects.all()
    serializer_class = serializers.ChainPostsSerializer


class ProjectsViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = serializers.ProjectSerializer
