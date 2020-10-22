from django.db import models
from accounts.models import User


class ChatRoom(models.Model):
    members = models.ManyToManyField(User, related_name="chat_rooms")


class Message(models.Model):
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
