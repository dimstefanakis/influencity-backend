from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from accounts.models import User


class React(models.Model):
    LIKE = 'L'
    DISLIKE = 'D'
    REACT_TYPES = (
        (LIKE, 'Like'),
        (DISLIKE, 'Dislike')
    )
    type = models.CharField(max_length=2,
                            choices=REACT_TYPES,
                            default=LIKE,)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reacts", null=True, blank=True)
