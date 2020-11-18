from django.db import models
from instructor.models import Coach
from djmoney.models.fields import MoneyField
from decimal import Decimal


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

    credit = MoneyField(max_digits=7, decimal_places=2, default_currency='USD')
    label = models.CharField(max_length=20, null=True, blank=True)
    subheading = models.CharField(max_length=30, null=True, blank=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="tiers")

    def __str__(self):
        return str(self.tier)

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
