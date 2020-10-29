from django.contrib import admin
from .models import Post, PostImage


class PostAdmin(admin.ModelAdmin):
    model = Post
    filter_horizontal = ('chained_posts',)


admin.site.register(Post, PostAdmin)
admin.site.register(PostImage)
