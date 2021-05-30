from django.db import models
from common.models import CommonImage


# TODO
# add default other option
class ExpertiseField(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)


class ExpertiseFieldAvatar(CommonImage):
    expertise_field = models.OneToOneField(ExpertiseField, blank=True, null=True,
                                           on_delete=models.CASCADE, related_name="avatar")

    def __str__(self):
        return str(self.expertise_field)


class ExpertiseFieldSuggestion(models.Model):
    name = models.CharField(max_length=100)
    suggested_by = models.ForeignKey('instructor.Coach', on_delete=models.CASCADE, null=True, blank=True, related_name="suggested_expertise")

    def __str__(self):
        return str(self.name)