from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from smart_selects.db_fields import ChainedManyToManyField
from common.models import CommonImage
from instructor.models import Coach
from tiers.models import Tier
from projects.models import Project
from reacts.models import React
import uuid


class Post(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    text = models.TextField(blank=True, null=True)
    text_html = models.TextField(blank=True, null=True)
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE, related_name="posts")
    linked_project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="posts", null=True, blank=True)
    reacts = GenericRelation(React)
    chained_posts = models.ManyToManyField('self', symmetrical=False, null=True, blank=True, related_name="parent_post")
    tiers = ChainedManyToManyField(
        Tier,
        chained_field="coach",
        chained_model_field="coach",
        auto_choose=True,
        related_name="posts",
        horizontal=True,
        null=True)

    def __str__(self):
        return self.text

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        if self.pk and not self.tiers.exists():#not self.coach.tiers.filter(tier__in=self.tiers).exists():
            self.tiers.add(self.coach.tiers.first())
        return super().save()

    class Meta:
        ordering = ('-created',)


class PostImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE)


class PostVideoAssetMetaData(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)


class PostVideo(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="videos")
    asset_id = models.CharField(max_length=120)


class PlaybackId(models.Model):
    policy = models.CharField(max_length=30)
    playback_id = models.CharField(max_length=100)
    video = models.ForeignKey(PostVideo, on_delete=models.CASCADE, related_name="playback_ids")
