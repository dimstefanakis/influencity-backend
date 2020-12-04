from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from accounts.models import User
from posts.models import Post
from common.models import CommonImage
from subscribers.models import Subscriber
import uuid


class Comment(MPTTModel):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    reply_to = models.ForeignKey(Subscriber, on_delete=models.CASCADE, null=True, blank=True, related_name="replyers")


class CommentImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="images")
