from django.apps import apps
from django.db import models
from django.db.models import JSONField
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.models import CommonUser, CommonImage
from uuid import uuid4
import stripe
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


class SubscriberAvatar(CommonImage):
    pass


class Subscriber(CommonUser):
    customer_id = models.CharField(max_length=30, null=True, blank=True)
    avatar = models.OneToOneField(SubscriberAvatar, on_delete=models.CASCADE, null=True, blank=True,
                                  related_name="subscriber")

    def save(self, *args, **kwargs):
        CoachAvatar = apps.get_model('instructor.CoachAvatar')

        # subscriber and coach operate on the same user so they should share avatars
        if self.user.is_coach:
            self.user.coach.name = self.name
            if self.avatar:
                if not self.user.coach.avatar:
                    coach_avatar = CoachAvatar.objects.create(image=self.avatar.image, height=self.avatar.height,
                        width=self.avatar.width)
                    self.user.coach.avatar = coach_avatar
                else:
                    # self.user.coach.avatar.delete()
                    coach_avatar = CoachAvatar.objects.create(image=self.avatar.image, height=self.avatar.height,
                        width=self.avatar.width)
                    self.user.coach.avatar = coach_avatar

                    # self.user.coach.avatar.image = self.avatar.image
                    # self.user.coach.avatar.height = self.avatar.height
                    # self.user.coach.avatar.width = self.avatar.width
            self.user.coach.save()
        super(Subscriber, self).save(*args, **kwargs)


class Subscription(models.Model):
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name="subscriptions")
    tier = models.ForeignKey('tiers.Tier', on_delete=models.CASCADE, related_name="subscriptions", null=True, blank=True)
    subscription_id = models.CharField(max_length=30, null=True, blank=True)
    customer_id = models.CharField(max_length=30, null=True, blank=True)
    # although this is available through the tier, tier always has the up to date price_id
    # but we sometimes need the old price_id
    price_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    json_data = JSONField(null=True, blank=True)


@receiver(pre_save, sender=Subscriber)
def create_stripe_customer(sender, instance, *args, **kwargs):
    if not instance.customer_id:
        customer = stripe.Customer.create(email=instance.user.email,
                               name=instance.name)
        instance.customer_id = customer.id
