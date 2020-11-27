from django.contrib import admin
from .models import ChatRoom, Message


class ChatRoomAdmin(admin.ModelAdmin):
    model = ChatRoom
    filter_horizontal = ('members',)


admin.site.register(ChatRoom, ChatRoomAdmin)
admin.site.register(Message)
