import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coach.settings')
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from .channelsmiddleware import JWTChannelMiddleware
import chat.routing
import posts.routing


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTChannelMiddleware(
        URLRouter([
            chat.routing.websocket_urlpatterns[0],
            posts.routing.websocket_urlpatterns[0]
        ])
    ),
})
