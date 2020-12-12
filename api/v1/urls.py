from django.urls import path, include
from django.conf.urls import url
from rest_framework import routers, serializers, viewsets
from . import views


# (?P<username>.+)
router = routers.DefaultRouter()
router.register(r'user/me', views.UserMeViewSet, basename="user_me")
router.register(r'subscriber/me', views.SubscriberMeViewSet, basename="subscriber_me")
router.register(r'users', views.UserViewSet)
router.register(r'my_coaches', views.MyCoachesViewSet, basename="my_coaches")
router.register(r'coaches', views.CoachViewSet)
router.register(r'posts', views.PostViewSet)
router.register(r'coach/(?P<surrogate>[0-9a-f-]+)/posts', views.CoachPostViewSet)
router.register(r'new_posts', views.NewPostsViewSet, basename="new_posts")
router.register(r'chained_posts', views.ChainedPostsViewSet, basename="create_chained_posts")
router.register(r'chain_posts', views.ChainPostsViewSet, basename="create_post_chain")
router.register(r'comments/create', views.CreateCommentViewSet, basename="create_comment")
router.register(r'comments/(?P<post_id>[0-9a-f-]+)', views.CommentsViewSet, basename="comments")
router.register(r'comment_replies/(?P<comment_id>[0-9a-f-]+)', views.CommentRepliesViewSet, basename="comment_replies")
router.register(r'projects/(?P<project_id>\d+)/teams', views.TeamsViewSet, basename="project_teams")
router.register(r'projects', views.ProjectsViewSet)
router.register(r'milestone_reports/(?P<milestone_id>\d+)', views.MilestoneCompletionReportViewSet)
router.register(r'my_projects', views.MyProjectsViewSet)
router.register(r'created_projects', views.MyCreatedProjectsViewSet)
router.register(r'expertise_fields', views.ExpertiseViewSet)
router.register(r'my_tiers', views.MyTiersViewSet, basename="my_tiers")
router.register(r'my_teams', views.MyTeamsViewSet, basename="my_teams")
router.register(r'reacts', views.ReactsViewSet)
router.register(r'my_chat_rooms/(?P<surrogate>[0-9a-f-]+)/messages', views.RoomMessagesViewSet,
                basename="chat_rooms_messages")
router.register(r'my_chat_rooms', views.MyChatRoomsViewSet, basename="my_chat_rooms")

urlpatterns = [
    path('v1/', include(router.urls)),
    path('v1/upload_video/', views.upload_video, name="upload_video"),
    path('v1/webhooks/upload_video_webhook/', views.upload_video_webhook, name="webhooks_upload_video"),
    path('v1/posts/<uuid:id>/change_react/', views.change_or_delete_react, name="change_or_delete_react"),
]
