from django.db import models
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from notifications.signals import notify
from asgiref.sync import async_to_sync
import channels.layers
from accounts.models import User
from subscribers.models import Subscriber
from projects.models import Project, Team
from common.models import CommonImage
from uuid import uuid4, uuid1
import re

class ChatRoom(models.Model):
    surrogate = models.UUIDField(default=uuid4, unique=True, db_index=True)
    TEAM = 'TM'
    TEAM_WITH_COACH = 'TC'
    GENERAL = 'GL'
    TYPES = [
        (TEAM, 'Team'),
        (TEAM_WITH_COACH, 'Team with coach'),
        (GENERAL, 'General')
    ]

    name = models.CharField(max_length=60, null=True, blank=True)
    type = models.CharField(max_length=2, choices=TYPES, default=TEAM)
    members = models.ManyToManyField(Subscriber, related_name="chat_rooms")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="chat_rooms")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="chat_rooms", null=True, blank=True)

    def __str__(self):
        if self.project:
            return "%s - Team" % self.project.name
        else:
            return ', '.join(self.members.all())


class Message(models.Model):
    surrogate = models.UUIDField(default=uuid4, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(Subscriber, on_delete=models.CASCADE, blank=False, null=False)
    text = models.TextField(blank=True, null=True)


class MessageImage(CommonImage):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="images")


class MessageVideoAssetMetaData(models.Model):
    passthrough = models.UUIDField(default=uuid1)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)


class MessageVideo(models.Model):
    passthrough = models.UUIDField(uuid1)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="videos")
    asset_id = models.CharField(max_length=120)


class MessagePlaybackId(models.Model):
    policy = models.CharField(max_length=30)
    playback_id = models.CharField(max_length=100)
    video = models.ForeignKey(MessageVideo, on_delete=models.CASCADE, related_name="playback_ids")


@receiver(m2m_changed, sender=ChatRoom.members.through)
def chat_room_members_changes(sender, instance, **kwargs):
    action = kwargs.pop('action', None)
    pk_set = kwargs.pop('pk_set', None)
    if action == "post_remove":
        # if there are no members left in the chat room delete it
        if instance.members.count() == 0:
            instance.delete()

@receiver(post_save, sender=Message, dispatch_uid="message_created")
def message_created(sender, instance, created, **kwargs):
    if created:
        channel_layer = channels.layers.get_channel_layer()

        # search for mentions in message and send notifications
        mentions = re.findall('@[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', instance.text)
        for mention in mentions:
            user_id = mention[1:]
            subscriber = Subscriber.objects.filter(surrogate=user_id)

            if subscriber.exists():
                notification_data = notify.send(instance.user, recipient=subscriber.first().user, 
                                                verb='mentioned you', action_object=instance.chat_room)

                notification = notification_data[0][1][0]
                async_to_sync(channel_layer.group_send)(
                    f"{str(subscriber.first().user.surrogate)}.notifications.group",
                    {
                        'type': 'send.notification',
                        'id': notification.id
                    }
                )