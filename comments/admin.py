from django.contrib import admin
from .models import Comment, CommentImage

admin.site.register(Comment)
admin.site.register(CommentImage)
