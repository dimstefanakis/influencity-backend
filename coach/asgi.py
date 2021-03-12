import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from .channelsmiddleware import JWTChannelMiddleware
import chat.routing
import posts.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTChannelMiddleware(
        URLRouter([
            chat.routing.websocket_urlpatterns[0],
            posts.routing.websocket_urlpatterns[0]
        ])
    ),
})
