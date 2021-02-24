from django.conf import settings
from django.db import models
from django.contrib.sites.models import Site
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import User
from subscribers.models import Subscriber
from expertisefields.models import ExpertiseField
from common.models import CommonUser, CommonImage
from uuid import uuid4
import os
import stripe


stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

class CoachAvatar(CommonImage):
    pass


class Coach(CommonUser):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="coach")
    surrogate = models.UUIDField(default=uuid4, db_index=True)
    avatar = models.ForeignKey(CoachAvatar, on_delete=models.CASCADE, null=True, blank=True, related_name="coach")
    subscribers = models.ManyToManyField(User, null=True, blank=True, related_name="coaches")
    expertise_field = models.ForeignKey(ExpertiseField, on_delete=models.CASCADE, null=True)
    bio = models.CharField(max_length=160, blank=True, null=True)

    # required for stripe
    stripe_id = models.CharField(max_length=40, null=True, blank=True)
    stripe_account_link = models.URLField(blank=True, null=True)
    charges_enabled = models.BooleanField(default=False)
    stripe_created = models.IntegerField(null=True, blank=True)
    stripe_expires_at = models.IntegerField(null=True, blank=True)

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
            except (FileNotFoundError, ObjectDoesNotExist) as e:
                self.subscriber.user.is_coach = True
                self.subscriber.user.save()
                avatar = None
                if self.subscriber.avatar:
                    avatar = CoachAvatar.objects.create(image=self.subscriber.avatar.image)
                Coach.objects.create(user=self.subscriber.user, name=self.subscriber.name, avatar=avatar)

        # TextField does not validate on db level so we validate here by getting only the first 5000 characters
        self.message = self.message[0:5000]
        super(CoachApplication, self).save(*args, **kwargs)


@receiver(pre_save, sender=Coach)
def setup_stripe_account(sender, instance, *args, **kwargs):

    if not instance.stripe_id:
        account = stripe.Account.create(
            type="express",
            country="GR",
            email=instance.user.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
        )

        if settings.DEBUG:
            redirect = 'http://localhost:3000/users/oauth/callback'
            refresh_url = "http://localhost:3000/reauth"
        else:
            redirect = 'https://%s%s' % (Site.objects.get_current().domain, '/users/oauth/callback')
            refresh_url = 'https://%s%s' % (Site.objects.get_current().domain, '/reauth')

        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=refresh_url,
            return_url=redirect,
            type="account_onboarding",
        )

        instance.stripe_id = account.id
        instance.stripe_account_link = account_link.url
        instance.stripe_created = account_link.created
        instance.stripe_expires_at = account_link.expires_at
