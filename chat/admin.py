from django.contrib import admin
from .models import ChatRoom, Message, MessageImage, MessageVideoAssetMetaData, MessageVideo, MessagePlaybackId


class ChatRoomAdmin(admin.ModelAdmin):
    model = ChatRoom
    filter_horizontal = ('members',)


admin.site.register(ChatRoom, ChatRoomAdmin)
admin.site.register(Message)
admin.site.register(MessageImage)
admin.site.register(MessageVideoAssetMetaData)
admin.site.register(MessageVideo)
admin.site.register(MessagePlaybackId)
