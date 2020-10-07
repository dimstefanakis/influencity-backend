from django.db import models
from instructor.models import Coach


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
    tier = models.CharField(
        max_length=2,
        choices=TIERS,
        default=FREE,
    )

    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="tiers")

    def __str__(self):
        return str(self.tier)
