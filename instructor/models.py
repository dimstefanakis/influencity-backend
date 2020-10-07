from django.db import models
from accounts.models import User
from expertisefields.models import ExpertiseField
from common.models import CommonUser, CommonImage


class Coach(CommonUser):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="coach")
    subscribers = models.ManyToManyField(User, null=True, related_name="coaches")
    expertise_field = models.ForeignKey(ExpertiseField, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return str(self.name)


class CoachAvatar(CommonImage):
    coach = models.OneToOneField(Coach, on_delete=models.CASCADE, null=True, related_name="avatar")

    def __str__(self):
        return "%s's avatar" % str(self.coach.name)
