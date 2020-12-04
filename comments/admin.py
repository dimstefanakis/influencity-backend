from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import Comment, CommentImage

admin.site.register(Comment, MPTTModelAdmin)
admin.site.register(CommentImage)
