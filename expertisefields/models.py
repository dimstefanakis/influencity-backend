from django.db import models
from common.models import CommonImage


class ExpertiseField(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)


class ExpertiseFieldAvatar(CommonImage):
    expertise_field = models.OneToOneField(ExpertiseField, blank=True, null=True,
                                           on_delete=models.CASCADE, related_name="avatar")

    def __str__(self):
        return str(self.expertise_field)
