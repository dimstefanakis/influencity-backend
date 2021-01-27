import os
from django.dispatch import receiver
from django.db import models
from django.db.models.signals import pre_save
from djmoney.models.fields import MoneyField
import stripe
from babel.numbers import get_currency_precision
from instructor.models import Coach
from accounts.models import User
from decimal import Decimal
import uuid

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
def money_to_integer(money):
    return int(
        money.amount * (
            10 ** get_currency_precision(money.currency.code)
        )
    )
class Tier(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tier', 'coach'], name='unique_tier')
        ]

    FREE = 'FR'
    TIER1 = 'T1'
    TIER2 = 'T2'
    TIER3 = 'T3'
    TIERS = [
        (FREE, 'Free'),
        (TIER1, 'Tier 1'),
        (TIER2, 'Tier 2'),
        (TIER3, 'Tier 3'),
    ]
    TIER_STRENGTH = [
        {'tier': FREE, 'strength': 0},
        {'tier': TIER1, 'strength': 1},
        {'tier': TIER2, 'strength': 2},
        {'tier': TIER3, 'strength': 3},
    ]
    tier = models.CharField(
        max_length=2,
        choices=TIERS,
        default=FREE,
    )

    surrogate = models.UUIDField(default=uuid.uuid4, null=True, blank=True)
    credit = MoneyField(max_digits=7, decimal_places=2, default_currency='USD')
    label = models.CharField(max_length=20, null=True, blank=True)
    subheading = models.CharField(max_length=30, null=True, blank=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="tiers")
    subscribers = models.ManyToManyField(User, null=True, blank=True, related_name="subscriptions")
    product_id = models.CharField(max_length=50, null=True, blank=True)
    price_id = models.CharField(max_length=50, null=True, blank=True)
    def __str__(self):
        return str(self.get_tier_display())

    def save(self, *args, **kwargs):
        if self.tier == self.FREE:
            self.credit = Decimal("0.00")
        elif self.tier == self.TIER1:
            self.credit = Decimal("5.00")
        if not self.label:
            if self.tier == self.FREE:
                self.label = 'Free'
            elif self.tier == self.TIER1:
                self.label = 'Casual'
            elif self.tier == self.TIER2:
                self.label = 'Basic'
            elif self.tier == self.TIER3:
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

    def __str__(self):
        return self.description


@receiver(pre_save, sender=Tier)
def tier_updated(sender, instance, *args, **kwargs):
    
    # create or change stripe Product
    if not instance.product_id:
        print(instance.credit)
        product = stripe.Product.create(name="%s - %s" % (instance.coach.name, instance.label))
        instance.product_id = product.id
    else:
        stripe.Product.modify(
            instance.product_id,
            metadata={"order_id": "6735"},
        )
    
    # create or update stripe Price
    if not instance.price_id:
        price = stripe.Price.create(
            unit_amount=money_to_integer(instance.credit),
            currency=instance.credit.currency.code.lower(),
            recurring={"interval": "month"},
            product=instance.product_id,
        )
        instance.price_id = price.id
    else:
        stripe.Price.modify(
            unit_amount=money_to_integer(instance.credit),
            currency=instance.credit.currency.code.lower(),
            recurring={"interval": "month"},
            product=instance.product_id,
        )
