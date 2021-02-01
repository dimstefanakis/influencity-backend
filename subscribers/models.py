from django.db import models
from common.models import CommonUser, CommonImage
from uuid import uuid4


class SubscriberAvatar(CommonImage):
    pass


class Subscriber(CommonUser):
    avatar = models.OneToOneField(SubscriberAvatar, on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="subscriber")

    def save(self, *args, **kwargs):
        # subscriber and coach operate on the same user so they should share avatars
        if self.user.is_coach:
            self.user.coach.name = self.name
            if self.avatar:
                self.user.coach.avatar.image = self.avatar.image
                self.user.coach.avatar.height = self.avatar.height
                self.user.coach.avatar.width = self.avatar.width
            self.user.coach.save()
        super(Subscriber, self).save(*args, **kwargs)


