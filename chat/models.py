from django.db import models
from accounts.models import User
from subscribers.models import Subscriber
from projects.models import Project
from common.models import CommonImage
from uuid import uuid4


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
    text = models.TextField(blank=False, null=False)


class MessageImage(CommonImage):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="images")
