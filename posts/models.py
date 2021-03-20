from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericRelation
from smart_selects.db_fields import ChainedManyToManyField
from notifications.signals import notify
from notifications.models import Notification
from asgiref.sync import async_to_sync
import channels.layers
from common.models import CommonImage
from instructor.models import Coach
from tiers.models import Tier
from projects.models import Project
from reacts.models import React
import uuid


class Post(models.Model):
    PROCESSING = 'PR'
    DONE = 'DO'
    STATUS_CHOICES = [
        (PROCESSING, 'Processing'),
        (DONE, 'Done')
    ]

    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    text = models.TextField(blank=True, null=True)
    text_html = models.TextField(blank=True, null=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="posts")
    linked_project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="posts", null=True, blank=True)
    reacts = GenericRelation(React)
    chained_posts = models.ManyToManyField('self', symmetrical=False, null=True, blank=True, related_name="parent_post")
    tiers = ChainedManyToManyField(
        Tier,
        chained_field="coach",
        chained_model_field="coach",
        auto_choose=True,
        related_name="all_posts",
        horizontal=True,
        null=True)
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE, related_name="posts", null=True)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=PROCESSING)
    
    def save(self, *args, **kwargs):
        # if 'processing' not in kwargs:
        #     # No need to process anything here, post is immidiately available
        #     self.status = self.DONE
        if self.pk and not self.tiers.exists():#not self.coach.tiers.filter(tier__in=self.tiers).exists():
            self.tiers.add(self.coach.tiers.first())
        return super().save()

    class Meta:
        ordering = ('-created',)


class PostImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE)


class PostVideoAssetMetaData(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)


class PostVideo(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="videos")
    asset_id = models.CharField(max_length=120)


class PlaybackId(models.Model):
    policy = models.CharField(max_length=30)
    playback_id = models.CharField(max_length=100)
    video = models.ForeignKey(PostVideo, on_delete=models.CASCADE, related_name="playback_ids")


# notifications sent to the subscribers after the coach posts
@receiver(post_save, sender=Post, dispatch_uid="post_created")
def post_created(sender, instance, created, **kwargs):
    if created:
        channel_layer = channels.layers.get_channel_layer()
        for sub in instance.tier.subscribers.all():
            notification_data = notify.send(instance.coach, recipient=sub, verb='just posted', action_object=instance)

            # this is the first time I am doing this
            # I don't honestly know why I am able to get the created the notification like this
            # but I cannot find an alternative so I will use it throughout this app
            notification = notification_data[0][1][0]
            async_to_sync(channel_layer.group_send)(
                f"{str(sub.surrogate)}.notifications.group",
                {
                    'type': 'send.notification',
                    'id': notification.id
                }
            )
