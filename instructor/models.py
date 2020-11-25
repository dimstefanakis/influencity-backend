from django.db import models
from accounts.models import User
from expertisefields.models import ExpertiseField
from common.models import CommonUser, CommonImage
from uuid import uuid4


class CoachAvatar(CommonImage):
    pass


class Coach(CommonUser):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="coach")
    surrogate = models.UUIDField(default=uuid4, db_index=True)
    avatar = models.ForeignKey(CoachAvatar, on_delete=models.CASCADE, null=True, blank=True, related_name="coach")
    subscribers = models.ManyToManyField(User, null=True, blank=True, related_name="coaches")
    expertise_field = models.ForeignKey(ExpertiseField, on_delete=models.CASCADE, null=True)
    bio = models.CharField(max_length=160, blank=True, null=True)

    def __str__(self):
        return str(self.name)
