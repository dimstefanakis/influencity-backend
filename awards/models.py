from django.db import models
from projects.models import Project, Milestone
from subscribers.models import Subscriber
import uuid

# Create your models here.
class AwardBase(models.Model):
    surrogate = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4)
    icon = models.ImageField(upload_to="awards")

    # this field is used for future usage
    # we may add dynamic models created by coaches
    # when this field is true the award is created by the Troosh team
    # else it's created by the coaches
    is_primary = models.BooleanField(default=False)
    xp = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return self.description


class Award(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE ,null=True, blank=True, related_name="awards")
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, null=True, blank=True, related_name="awards")
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="awards")
    award = models.ForeignKey(AwardBase, on_delete=models.CASCADE, related_name="awards", null=True, blank=True)