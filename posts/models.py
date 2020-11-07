import os
import time
import mux_python
from mux_python.rest import ApiException
from django.db import models
from django.conf import settings
from django.core.files.storage import Storage
from smart_selects.db_fields import ChainedManyToManyField
from common.models import CommonImage
from instructor.models import Coach
from tiers.models import Tier
import uuid
from pprint import pprint


class MuxStorage(Storage):
    configuration = mux_python.Configuration()
    configuration.username = os.environ['MUX_TOKEN_ID']
    configuration.password = os.environ['MUX_TOKEN_SECRET']

    # create an instance of the API class
    api_instance = mux_python.DirectUploadsApi(mux_python.ApiClient(configuration))
    input_settings = [mux_python.InputSettings(url='https://storage.googleapis.com/muxdemofiles/mux-video-intro.mp4')]
    create_asset_request = mux_python.CreateAssetRequest(input=input_settings,
                                                         playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
                                                         mp4_support="standard")

    create_upload_request = mux_python.CreateUploadRequest(
        new_asset_settings=create_asset_request,
        test=True)

    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs)

    def _save(self, name, content):
        try:
            # Create a new direct upload URL
            api_response = self.api_instance.create_direct_upload(self.create_upload_request)
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling DirectUploadsApi->create_direct_upload: %s\n" % e)


class Post(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
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
        if self.pk and not self.tiers.exists():#not self.coach.tiers.filter(tier__in=self.tiers).exists():
            self.tiers.add(self.coach.tiers.first())
        return super().save()

    class Meta:
        ordering = ('-created_at',)


class PostImage(CommonImage):
    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    coach = models.ForeignKey(Coach, on_delete=models.CASCADE)


class PostVideo(models.Model):
    video = models.FileField()
