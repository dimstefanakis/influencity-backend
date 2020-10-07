from django.db import models
from subscribers.models import Subscriber


class Project(models.Model):
    EASY = 'EA'
    INTERMEDIATE = 'IM'
    ADVANCED = 'AD'
    DIFFICULTIES = [
        (EASY, 'Easy'),
        (INTERMEDIATE, 'Intermediate'),
        (ADVANCED, 'Advanced'),
    ]

    difficulty = models.CharField(
        max_length=2,
        choices=DIFFICULTIES,
        default=EASY,
    )
    name = models.CharField(max_length=200, blank=False, null=False, default="")
    description = models.TextField(max_length=2000, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField(default=1, blank=False, null=False)

    def __str__(self):
        return self.name


class Prerequisite(models.Model):
    prerequisite = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="prerequisites")

    def __str__(self):
        return self.prerequisite


class ProgressLevel(models.Model):
    level = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="progress_levels")

    def __str__(self):
        return self.level


class Team(models.Model):
    members = models.ManyToManyField(Subscriber, related_name="teams")
