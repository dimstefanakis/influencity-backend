from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import User
from subscribers.models import Subscriber
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


class CoachApplication(models.Model):
    PENDING = 'PD'
    APPROVED = 'AP'
    REJECTED = 'RJ'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected')
    ]
    surrogate = models.UUIDField(default=uuid4, db_index=True)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="applications")
    message = models.TextField(null=False, blank=False)
    approved = models.BooleanField(default=False)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=PENDING)

    def save(self, *args, **kwargs):
        
        # Automatically create a coach account when the application gets approved
        if self.status == self.APPROVED:
            try:
                coach = self.subscriber.user.coach
            # Only create coach account if it doesn't exist
            except ObjectDoesNotExist:
                self.subscriber.user.is_coach = True
                self.subscriber.user.save()
                avatar = None
                if self.subscriber.avatar:
                    avatar = CoachAvatar.objects.create(image=self.subscriber.avatar.image)
                Coach.objects.create(user=self.subscriber.user, name=self.subscriber.name, avatar=avatar)

        # TextField does not validate on db level so we validate here by getting only the first 5000 characters
        self.message = self.message[0:5000]
        super(CoachApplication, self).save(*args, **kwargs)
