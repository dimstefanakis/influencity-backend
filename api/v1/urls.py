from django.urls import path, include
from django.conf.urls import url
from rest_framework import routers, serializers, viewsets
from . import views


# (?P<username>.+)
router = routers.DefaultRouter()
router.register(r'user/me', views.UserMeViewSet, basename="user_me")
router.register(r'users', views.UserViewSet)
router.register(r'coaches', views.CoachViewSet)
router.register(r'posts', views.PostViewSet)
router.register(r'new_posts', views.NewPostsViewSet, basename="new_posts")
router.register(r'chained_posts', views.ChainedPostsViewSet, basename="create_chained_posts")
router.register(r'chain_posts', views.ChainPostsViewSet, basename="create_post_chain")
router.register(r'projects/(?P<project_id>\d+)/teams', views.TeamsViewSet, basename="project_teams")
router.register(r'projects', views.ProjectsViewSet)
router.register(r'my_projects', views.MyProjectsViewSet)
router.register(r'created_projects', views.MyCreatedProjectsViewSet)
router.register(r'expertise_fields', views.ExpertiseViewSet)

urlpatterns = [
    path('v1/', include(router.urls))
]
