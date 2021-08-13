from django.db import models
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from notifications.signals import notify
from notifications.models import Notification
from asgiref.sync import async_to_sync
import channels.layers
from subscribers.models import Subscriber
from common.models import CommonImage
from instructor.models import Coach
from accounts.models import User
from djmoney.models.fields import MoneyField
from babel.numbers import get_currency_precision
import uuid
import stripe
import os

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def money_to_integer(money):
    return int(
        money.amount * (
            10 ** get_currency_precision(money.currency.code)
        )
    )

def create_stripe_price(instance):
    price = stripe.Price.create(
        unit_amount=money_to_integer(instance.credit),
        currency=instance.credit.currency.code.lower(),
        product=instance.product_id,
    )

    return price


class Project(models.Model):
    EASY = 'EA'
    INTERMEDIATE = 'IM'
    ADVANCED = 'AD'
    DIFFICULTIES = [
        (EASY, 'Easy'),
        (INTERMEDIATE, 'Intermediate'),
        (ADVANCED, 'Advanced'),
    ]

    difficulty = models.CharField(
        max_length=2,
        choices=DIFFICULTIES,
        default=EASY,
    )

    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    coach = models.ForeignKey(Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="created_projects")
    name = models.CharField(max_length=200, blank=False, null=False, default="")
    description = models.TextField(max_length=2000, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField(default=1, blank=False, null=False)
    members = models.ManyToManyField(Subscriber, blank=True, related_name="projects")
    credit = MoneyField(max_digits=7, decimal_places=2, default_currency='EUR', default=10, null=True, blank=True)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    price_id = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.product_id:
            product = stripe.Product.create(name="%s - %s" % (self.coach.name, self.name))
            self.product_id = product.id
        else:
            pass
        price = create_stripe_price(self)
        self.price_id = price.id
        return super().save()


class TeamImage(CommonImage):
    pass


class Team(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    name = models.CharField(max_length=60, null=True, blank=True)
    avatar = models.ForeignKey(TeamImage, on_delete=models.CASCADE, null=True, blank=True, related_name="team")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="teams", null=True)
    members = models.ManyToManyField(Subscriber, related_name="teams")

    def __str__(self):
        return self.name


class Prerequisite(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="prerequisites")

    def __str__(self):
        return self.description


class Milestone(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    completed_teams = models.ManyToManyField('Team', blank=True, related_name="milestones_completed")

    def __str__(self):
        return self.description


class MilestoneCompletionReport(models.Model):
    PENDING = 'PD'
    ACCEPTED = 'AC'
    REJECTED = 'RJ'
    STATUSES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    ]

    PROCESSING = 'PR'
    DONE = 'DO'
    STATUS_CHOICES = [
        (PROCESSING, 'Processing'),
        (DONE, 'Done')
    ]

    status = models.CharField(
        max_length=2,
        choices=STATUSES,
        default=PENDING,
    )
    
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    video_status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=PROCESSING)
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="reports", null=True, blank=True)
    members = models.ManyToManyField(Subscriber, related_name="milestone_reports")
    message = models.TextField(null=True, blank=True)
    coach_feedback = models.TextField(null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name="milestone_completion_reports")


class MilestoneCompletionImage(CommonImage):
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE, null=True,
                                                    blank=True, related_name="images")


class MilestoneCompletionVideoAssetMetaData(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE)


class MilestoneCompletionVideo(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE, related_name="videos")
    asset_id = models.CharField(max_length=120)


class MilestoneCompletionPlaybackId(models.Model):
    policy = models.CharField(max_length=30)
    playback_id = models.CharField(max_length=100)
    video = models.ForeignKey(MilestoneCompletionVideo, on_delete=models.CASCADE, related_name="playback_ids")


class Coupon(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, null=True, blank=True, related_name="coupons")
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, null=True, blank=True, related_name="coupons")
    coupon_id = models.CharField(max_length=30, null=True, blank=True)
    valid = models.BooleanField(default=True)
    json_data = models.JSONField(null=True, blank=True)


@receiver(pre_save, sender=Project)
def project_updated(sender, instance, *args, **kwargs):
    # create stripe Product
    if not instance.product_id:
        product = stripe.Product.create(name="%s - %s" % (instance.coach.name, instance.name))
        instance.product_id = product.id
    else:
        pass

    if not instance.price_id:
        price = create_stripe_price(instance)
        instance.price_id = price.id


@receiver(m2m_changed, sender=Team.members.through)
def team_members_changed(sender, instance, **kwargs):
    action = kwargs.pop('action', None)
    pk_set = kwargs.pop('pk_set', None)    
    if action == "post_remove":
        # if teams is left with no members delete it
        if instance.members.count() == 0:
            instance.delete()


@receiver(post_save, sender=MilestoneCompletionReport)
def milestone_completion_report_saved(sender, instance, created, **kwargs):
    if instance.status == MilestoneCompletionReport.ACCEPTED:
        instance.milestone.completed_teams.add()        


# this notification sends notification to the coach after the team completes a milestone
# we first need to wait for the members to be populated and then send the notification thats why
# we handle the milestone creation report in two signals
@receiver(m2m_changed, sender=MilestoneCompletionReport.members.through)
def milestone_completion_report_notification_to_coach(sender, instance, **kwargs):
    action = kwargs.pop('action', None)
    pk_set = kwargs.pop('pk_set', None)    
    if action == "post_add":
        channel_layer = channels.layers.get_channel_layer()
        notification_data = notify.send(instance.members.first().user, recipient=instance.milestone.project.coach.user, verb='completed a milestone', action_object=instance)

        notification = notification_data[0][1][0]
        async_to_sync(channel_layer.group_send)(
            f"{str(instance.milestone.project.coach.user.surrogate)}.notifications.group",
            {
                'type': 'send.notification',
                'id': notification.id
            }
        )


@receiver(post_save, sender=MilestoneCompletionReport, dispatch_uid="send_notification")
def milestone_completion_report_notification(sender, instance, created, **kwargs):
    channel_layer = channels.layers.get_channel_layer()
    if not created:
        if instance.status == MilestoneCompletionReport.ACCEPTED:
            for sub in instance.members.all():
                notification_data = notify.send(instance.milestone.project.coach.user, recipient=sub.user, verb='marked your milestone as complete!', action_object=instance)

                notification = notification_data[0][1][0]
                async_to_sync(channel_layer.group_send)(
                    f"{str(sub.user.surrogate)}.notifications.group",
                    {
                        'type': 'send.notification',
                        'id': notification.id
                    }
                )
        elif instance.status == MilestoneCompletionReport.REJECTED:
            for sub in instance.members.all():
                notification_data = notify.send(instance.milestone.project.coach.user, recipient=sub.user, verb='marked your milestone as rejected', action_object=instance)

                notification = notification_data[0][1][0]
                async_to_sync(channel_layer.group_send)(
                    f"{str(sub.user.surrogate)}.notifications.group",
                    {
                        'type': 'send.notification',
                        'id': notification.id
                    }
                )
