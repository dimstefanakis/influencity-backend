from django.db import models
from smart_selects.db_fields import ChainedManyToManyField
from common.models import CommonImage
from instructor.models import Coach
from tiers.models import Tier
import uuid


class Post(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    text = models.TextField(blank=True, null=True)
    text_html = models.TextField(blank=True, null=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="posts")
    chained_posts = models.ManyToManyField('self', symmetrical=False, null=True, blank=True, related_name="parent_post")
    tiers = ChainedManyToManyField(
        Tier,
        chained_field="coach",
        chained_model_field="coach",
        auto_choose=True,
        related_name="posts",
        horizontal=True,
        null=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if not self.tiers.exists():#not self.coach.tiers.filter(tier__in=self.tiers).exists():
            self.tiers.add(self.coach.tiers.first())
        return super().save()


class PostImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE)
