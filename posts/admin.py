from django.contrib import admin
from .models import Post, PostImage, PostVideoAssetMetaData, PostVideo


class PostAdmin(admin.ModelAdmin):
    model = Post
    filter_horizontal = ('chained_posts',)


admin.site.register(Post, PostAdmin)
admin.site.register(PostImage)
admin.site.register(PostVideoAssetMetaData)
admin.site.register(PostVideo)
