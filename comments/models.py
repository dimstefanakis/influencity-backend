from django.db import models
from accounts.models import User
from posts.models import Post
from common.models import CommonImage
import uuid


class Comment(models.Model):
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")


class CommentImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="images")
