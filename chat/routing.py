from django.conf.urls import url

from . import consumers

websocket_urlpatterns = [
    url(r'ws/chat/(?P<room_name>[0-9a-f-]+)/$', consumers.ChatConsumer.as_asgi()),
]
