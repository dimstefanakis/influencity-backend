from django.urls import path, include
from django.conf.urls import url
from rest_framework import routers, serializers, viewsets
from push_notifications.api.rest_framework import APNSDeviceAuthorizedViewSet, GCMDeviceAuthorizedViewSet
from . import views


# (?P<username>.+)
router = routers.DefaultRouter()
router.register(r'user/me', views.UserMeViewSet, basename="user_me")
#router.register(r'subscriber/me', views.SubscriberMeViewSet, basename="subscriber_me")
router.register(r'users', views.UserViewSet)
router.register(r'coach_application', views.CoachApplicationViewSet, basename="coach_application")
router.register(r'my_coaches', views.MyCoachesViewSet, basename="my_coaches")
router.register(r'coaches', views.CoachViewSet)
router.register(r'posts', views.PostViewSet)
router.register(r'awards/create', views.CreateAwardViewSet)
router.register(r'awards', views.AwardBaseViewSet)
router.register(r'my_awards', views.MyAwardsViewSet, basename="my_awards")
router.register(r'coach/(?P<surrogate>[0-9a-f-]+)/posts', views.CoachPostViewSet)
router.register(r'new_posts', views.NewPostsViewSet, basename="new_posts")
router.register(r'chained_posts', views.ChainedPostsViewSet, basename="create_chained_posts")
router.register(r'chain_posts', views.ChainPostsViewSet, basename="create_post_chain")
router.register(r'comments/create', views.CreateCommentViewSet, basename="create_comment")
router.register(r'comments/(?P<post_id>[0-9a-f-]+)', views.CommentsViewSet, basename="comments")
router.register(r'comment_replies/(?P<comment_id>[0-9a-f-]+)', views.CommentRepliesViewSet, basename="comment_replies")
router.register(r'projects/(?P<project_id>[0-9a-f-]+)/teams', views.TeamsViewSet, basename="project_teams")
router.register(r'projects/(?P<project_id>[0-9a-f-]+)/posts', views.ProjectPostsViewSet, basename="project_posts")
router.register(r'projects', views.ProjectsViewSet)
router.register(r'my_coaches_projects', views.MyCoachesProjectsViewSet)
router.register(r'milestone_reports/(?P<milestone_id>\d+)', views.MilestoneCompletionReportViewSet)
router.register(r'my_projects', views.MyProjectsViewSet)
router.register(r'created_projects', views.MyCreatedProjectsViewSet)
router.register(r'expertise_fields', views.ExpertiseViewSet)
router.register(r'my_coupons', views.MyCouponsViewSet, basename="my_coupons")
router.register(r'my_tiers', views.MyTiersViewSet, basename="my_tiers")
router.register(r'my_teams', views.MyTeamsViewSet, basename="my_teams")
router.register(r'reacts', views.ReactsViewSet)
router.register(r'notifications', views.NotificationsViewSet, basename="notifications")
router.register(r'my_chat_rooms/(?P<surrogate>[0-9a-f-]+)/messages', views.RoomMessagesViewSet,
                basename="chat_rooms_messages")
router.register(r'my_chat_rooms', views.MyChatRoomsViewSet, basename="my_chat_rooms")
router.register(r'create_message', views.CreateMessageViewSet, basename="create_message")
router.register(r'device/apns', APNSDeviceAuthorizedViewSet)
router.register(r'device/gcm', GCMDeviceAuthorizedViewSet)

urlpatterns = [
    path('v1/', include(router.urls)),
    path('v1/subscriber/me/', views.subscriber_me, name="subscriber_me"),
    path('v1/coach/me/', views.coach_me, name="coach_me"),
    path('v1/subscribe/<uuid:id>', views.subscribe, name="subscribe"),
    path('v1/mark_last_seen_post/', views.mark_last_seen_post, name="mark_last_seen_post"),
    path('v1/unseen_post_count/', views.get_unseen_post_count, name="get_unseen_post_count"),
    path('v1/unseen_posts/', views.get_unseen_posts, name="get_unseen_posts"),
    path('v1/create_stripe_subscription/<uuid:id>', views.create_stripe_subscription, name="create_stripe_subscription"),
    path('v1/cancel_subscription/<uuid:id>', views.cancel_subscription, name="cancel_subscription"),
    path('v1/preview_subscription_invoice/<str:id>', views.preview_subscription_invoice, name="preview_subscription_invoice"),
    path('v1/check_payment_intent_status/<str:id>', views.check_payment_intent_status, name="check_payment_intent_status"),
    path('v1/check_subscription_status/<str:id>', views.check_subscription_status, name="check_subscription_status"),
    path('v1/join_project/<uuid:id>', views.join_project, name="join_project"),
    path('v1/project_payment_sheet/<uuid:id>', views.project_payment_sheet, name="project_payment_sheet"),
    path('v1/unread_notifications_count/', views.get_unread_count, name="get_unread_count"),
    path('v1/mark_all_notifications_as_read/', views.mark_all_read, name="mark_all_notifications_as_read"),
    path('v1/attach_payment_method/', views.attach_payment_method, name="attach_payment_method"),
    path('v1/get_payment_method/', views.get_payment_method, name="get_payment_method"),
    path('v1/upload_video/', views.upload_video, name="upload_video"),
    path('v1/upload_milestonecompletion_video/', views.upload_milestonecompletion_video, name="upload_milestonecompletion_video"),
    path('v1/webhooks/upload_video_webhook/', views.upload_video_webhook, name="webhooks_upload_video"),
    path('v1/webhooks/stripe/', views.stripe_webhook, name="stripe_webhook"),
    path('v1/create_stripe_account_link/', views.create_stripe_account_link, name="create_stripe_account_link"),
    path('v1/get_stripe_balance/', views.get_stripe_balance, name="get_stripe_balance"),
    path('v1/get_stripe_login_link/', views.get_stripe_login, name="get_stripe_login_link"),
    path('v1/posts/<uuid:id>/change_react/', views.change_or_delete_react, name="change_or_delete_react"),
    path('v1/comment/<uuid:id>/change_react/', views.change_or_delete_comment_react, name="change_or_delete_comment_react"),
    path('v1/milestone_report/<uuid:milestone_report_id>/update/', views.update_milestone_report_from_task_id, name="update_milestone_report_from_task_id"),
    path('v1/select_expertise/', views.select_expertise, name="select_expertise"),
]
