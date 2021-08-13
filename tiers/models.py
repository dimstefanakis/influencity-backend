import os
from django.dispatch import receiver
from django.db import models
from django.db.models.signals import pre_save, post_save
from djmoney.models.fields import MoneyField
import stripe
from babel.numbers import get_currency_precision
from instructor.models import Coach
from accounts.models import User
from subscribers.models import Subscription
from decimal import Decimal
import uuid
import json

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
        recurring={"interval": "month"},
        product=instance.product_id,
    )

    return price


class Tier(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tier', 'coach'], name='unique_tier')
        ]

    FREE = 'FR'
    TIER1 = 'T1'
    TIER2 = 'T2'
    TIERS = [
        (FREE, 'Free'),
        (TIER1, 'Tier 1'),
        (TIER2, 'Tier 2'),
    ]
    TIER_STRENGTH = [
        {'tier': FREE, 'strength': 0},
        {'tier': TIER1, 'strength': 1},
        {'tier': TIER2, 'strength': 2},
    ]
    tier = models.CharField(
        max_length=2,
        choices=TIERS,
        default=FREE,
    )

    surrogate = models.UUIDField(default=uuid.uuid4, null=True, blank=True)
    credit = MoneyField(max_digits=7, decimal_places=2, default_currency='EUR')
    label = models.CharField(max_length=20, null=True, blank=True)
    subheading = models.CharField(max_length=30, null=True, blank=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="tiers")
    subscribers = models.ManyToManyField(User, null=True, blank=True, related_name="deprecated_subscriptions")
    #subscriptions = models.ManyToManyField(Subscription, null=True, blank=True, related_name="subscriptions")
    product_id = models.CharField(max_length=50, null=True, blank=True)
    price_id = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return str(self.get_tier_display())

    def save(self, *args, **kwargs):
        if self.pk:
            # checking if price has changed
            old_tier = Tier.objects.filter(pk=self.pk).first()
            if old_tier.credit != self.credit:
                price = create_stripe_price(self)

                # following these instructions https://stripe.com/docs/billing/subscriptions/products-and-prices
                # to update the subscription pricing
                # finding all the subscriptions with the old price id
                subscriptions = Subscription.objects.filter(price_id=self.price_id)
                for sub_instance in subscriptions:
                    subscription = stripe.Subscription.retrieve(sub_instance.subscription_id)
                
                    subscription = stripe.Subscription.modify(
                        subscription.id,
                        cancel_at_period_end=False,
                        proration_behavior='create_prorations',
                        items=[{
                            'id': subscription['items']['data'][0].id,
                            'price': price.id,
                        }]
                    )

                    sub_instance.json_data = json.dumps(subscription)
                    sub_instance.subscription_id = subscription.id
                    # subscribe user to the new pricing
                    sub_instance.price_id = price.id
                    sub_instance.save()
                
                # update the price_id
                self.price_id = price.id

        if self.tier == self.FREE:
            self.credit = Decimal("0.00")
        elif self.tier == self.TIER1:
            self.credit = Decimal("7.00")
        else:
            # Set the default premium pricing to 10
            if not self.credit:
                self.credit = Decimal("10.00")
        if not self.label:
            if self.tier == self.FREE:
                self.label = 'Free'
            elif self.tier == self.TIER1:
                self.label = 'Basic'
            elif self.tier == self.TIER2:
                self.label = 'Premium'
        if not self.subheading:
            if self.tier == self.FREE:
                self.subheading = 'Free for everyone'
            else:
                self.subheading = f"{self.credit}/month"
        super(Tier, self).save(*args, **kwargs)


class Benefit(models.Model):
    description = models.CharField(max_length=80, null=False, blank=False)
    tier = models.ForeignKey(Tier, on_delete=models.CASCADE, null=False, blank=False, related_name="benefits")
    editable = models.BooleanField(default=True)

    def __str__(self):
        return self.description


@receiver(pre_save, sender=Tier)
def tier_updated(sender, instance, *args, **kwargs):
    # create stripe Product
    if not instance.product_id:
        product = stripe.Product.create(name="%s - %s" % (instance.coach.name, instance.label))
        instance.product_id = product.id
    else:
        pass
    
    # create stripe Price
    if not instance.price_id:
        price = create_stripe_price(instance)
        instance.price_id = price.id


@receiver(post_save, sender=Coach)
def create_tiers(sender, instance, created, **kwargs):
    if created:
        Tier.objects.create(coach=instance, tier=Tier.FREE)
        Tier.objects.create(coach=instance, tier=Tier.TIER1)
        #Tier.objects.create(coach=instance, tier=Tier.TIER2)
