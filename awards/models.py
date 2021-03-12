from django.db import models
from projects.models import Project
from subscribers.models import Subscriber

# Create your models here.
class AwardBase(models.Model):
    icon = models.ImageField(upload_to="awards")

    # this field is used for future usage
    # we may add dynamic models created by coaches
    # when this field is true the award is created by the Troosh team
    # else it's created by the coaches
    is_primary = models.BooleanField(default=False)
    description = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.description


class Award(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="awards")
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="awards")
    award = models.ForeignKey(AwardBase, on_delete=models.CASCADE, related_name="awards", null=True, blank=True)