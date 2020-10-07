from django.db import models
from accounts.models import User
import uuid


class CommonImage(models.Model):
    class Meta:
        abstract = True

    height = models.IntegerField()
    width = models.IntegerField()
    image = models.ImageField(upload_to='images', null=True, blank=True, height_field='height',
                              width_field='width')


class CommonUser(models.Model):
    class Meta:
        abstract = True

    surrogate = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, blank=False, null=False, default="")
