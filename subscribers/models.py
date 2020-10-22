from django.db import models
from common.models import CommonUser, CommonImage


class SubscriberAvatar(CommonImage):
    pass


class Subscriber(CommonUser):
    avatar = models.ForeignKey(SubscriberAvatar, on_delete=models.CASCADE, null=True, blank=True,
                               related_name="subscriber")

