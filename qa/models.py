from django.dispatch import receiver
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.core.mail import send_mail
from djmoney.models.fields import MoneyField
from instructor.models import Coach
import uuid
import os
import stripe
from babel.numbers import get_currency_precision


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


class Question(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    answer_needed_now = models.BooleanField(default=False)
    initial_delivery_time = models.DateTimeField(null=True, blank=True)
    delivery_time = models.DateTimeField(null=True, blank=True)
    delivered_by = models.ForeignKey(
        Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="assigned_questions")
    body = models.TextField(blank=True, null=True)

    zoom_link = models.URLField(null=True, blank=True)
    zoom_password = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.body or ''


class QuestionInvitation(models.Model):
    PENDING = 'PD'
    ACCEPTED = 'AC'
    DECLINED = 'DC'
    STATUSES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
    ]

    status = models.CharField(
        max_length=2,
        choices=STATUSES,
        default=PENDING,
    )

    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    question = models.ForeignKey(
        Question, blank=True, null=True, on_delete=models.CASCADE, related_name="invitations")
    coach = models.ForeignKey(Coach, blank=True, null=True,
                              on_delete=models.CASCADE, related_name="invitations")

    def __str__(self):
        return f"{self.coach.name} - {self.question}"


class QaSession(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    coach = models.ForeignKey(Coach, blank=True, null=True,
                              on_delete=models.CASCADE, related_name="qa_sessions")
    minutes = models.PositiveSmallIntegerField(
        default=15, blank=False, null=False)
    credit = MoneyField(max_digits=7, decimal_places=2,
                        default_currency='EUR', default=15, null=True, blank=True)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    price_id = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.coach.name} - {self.minutes} minute session"

    def save(self, *args, **kwargs):
        if not self.product_id:
            product = stripe.Product.create(
                name=f"{self.coach.name} - {self.minutes} minute session")
            self.product_id = product.id
        else:
            pass

        if not self.price_id:
            price = create_stripe_price(self)
            self.price_id = price.id
        return super().save()


class AvailableTimeRange(models.Model):
    WEEKDAYS = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]

    weekday = models.IntegerField(choices=WEEKDAYS)
    coach = models.ForeignKey(
        Coach, on_delete=models.CASCADE, related_name="available_time_ranges")
    start_time = models.TimeField()
    end_time = models.TimeField()


class CommonQuestion(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    coach = models.ForeignKey(
        Coach, on_delete=models.CASCADE, related_name="common_questions")
    body = models.TextField()


@receiver(post_save, sender=QuestionInvitation)
def question_invitation_created(sender, instance, created, *args, **kwargs):
    if created:
        send_mail(
            f"Someone needs your expertise!",
            f"""
            A person needs an answer for this question:
            {instance.question.body}

            Click here to notify the user that you are available to answer this questions: 
            https://questions.troosh.app/?qiid={instance.surrogate}&accept=true

            Note that the user ultimately decides if they want to book a call with you!
            """,
            'beta@troosh.app',
            [instance.coach.user.email],
            fail_silently=False,
        )


@receiver(pre_save, sender=QaSession)
def qa_session_updated(sender, instance, *args, **kwargs):
    # create stripe Product
    if not instance.product_id:
        product = stripe.Product.create(
            name=f"{instance.coach.name} - {instance.minutes} minute session")
        instance.product_id = product.id
    else:
        pass

    # create stripe Price
    if not instance.price_id:
        price = create_stripe_price(instance)
        instance.price_id = price.id


def get_credits_for_x_minutes(credit_15_min, minutes):
    return minutes * credit_15_min / 15


@receiver(post_save, sender=Coach)
def create_sessions(sender, instance, created, **kwargs):
    credit_15_minutes = instance.qa_session_credit / 2

    if created or instance.qa_sessions.count() == 0:
        QaSession.objects.create(
            coach=instance, credit=get_credits_for_x_minutes(credit_15_minutes, 15), minutes=15)
        QaSession.objects.create(
            coach=instance, credit=get_credits_for_x_minutes(credit_15_minutes, 30), minutes=30)
        QaSession.objects.create(
            coach=instance, credit=get_credits_for_x_minutes(credit_15_minutes, 45), minutes=45)
        QaSession.objects.create(
            coach=instance, credit=get_credits_for_x_minutes(credit_15_minutes, 65), minutes=60)
    else:
        # update every qa session (15 mins, 30 mins etc) based on the coaches new rates
        for qa_session in instance.qa_sessions.all():
            qa_session.credit = get_credits_for_x_minutes(
                credit_15_minutes, qa_session.minutes)
            qa_session.save()

            price = create_stripe_price(qa_session)
            qa_session.price_id = price.id
