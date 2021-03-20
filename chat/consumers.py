# chat/consumers.py
import json
import re
from asgiref.sync import async_to_sync
from channels.auth import get_user
from channels.generic.websocket import WebsocketConsumer, AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from subscribers.models import Subscriber
from chat.models import Message, ChatRoom


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # self.user = await self.get_subscriber(self.scope['user'])
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'chat_%s' % self.room_name

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        self.user = await self.get_subscriber(self.scope['user'])
        data = json.loads(text_data)
        subscriber = self.user
        message = data['text']
        room = data['room']
        self.room = await self.get_chat_room(room)
        self.user_avatar = await self.get_subscriber_avatar(subscriber) #await self.get_user_avatar(user)
        new_message = await self.create_message(text=message, user=subscriber, room=self.room)
        try:
            avatar = self.user_avatar.image.url
        except KeyError:
            avatar = None

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': new_message.text,
                # messages incoming to this websocket will not handle images
                # image messages are handle through a regular http api request
                'images': json.dumps([]),
                'message_id': str(new_message.surrogate),
                'user_id': str(new_message.user.surrogate),
                'user_name': new_message.user.name,
                'user_avatar': avatar,
                'room': str(new_message.chat_room.surrogate)
            }
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        message_id = event['message_id']
        user_id = event['user_id']
        user_name = event['user_name']
        user_avatar = event['user_avatar']
        images = event['images']
        room = event['room']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'message_id': message_id,
            'user_id': user_id,
            'user_name': user_name,
            'user_avatar': user_avatar,
            'images': images,
            'room': room
        }))

    @database_sync_to_async
    def get_user(self, user):
        return Subscriber.objects.get(surrogate=user)

    @database_sync_to_async
    def get_user_avatar(self, user):
        return Subscriber.objects.get(surrogate=user).avatar

    @database_sync_to_async
    def get_chat_room(self, room):
        return ChatRoom.objects.get(surrogate=room)

    @database_sync_to_async
    def create_message(self, text, user, room):
        return Message.objects.create(text=text, user=user, chat_room=room)

    @database_sync_to_async
    def get_subscriber(self, user):
        return user.subscriber

    @database_sync_to_async
    def get_subscriber_avatar(self, subscriber):
        return subscriber.avatar
