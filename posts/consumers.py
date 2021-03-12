from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from notifications.models import Notification
import json

class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope['user']

        # join user specific layer
        await self.channel_layer.group_add(
            f"{str(user.surrogate)}.notitifactions.group",
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        user = self.scope['user']
        
        # disconnect from group
        await self.channel_layer.group_discard(
            f"{str(user.surrogate)}.notitifactions.group",
            self.channel_name
        )

    async def send_notification(self, event):
        notification_id = event['id']
        # notification = Notification.objects.get(pk=notification_id)

        await self.send(text_data=json.dumps({
            'id': notification_id
        }))

    @database_sync_to_async
    def get_notification(self, notification_id):
        notification = Notification.objects.get(pk=notification_id)
        return notification
