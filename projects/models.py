from django.db import models
from subscribers.models import Subscriber
from common.models import CommonImage
from instructor.models import Coach


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

    coach = models.ForeignKey(Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="created_projects")
    name = models.CharField(max_length=200, blank=False, null=False, default="")
    description = models.TextField(max_length=2000, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField(default=1, blank=False, null=False)
    members = models.ManyToManyField(Subscriber, blank=True, related_name="projects")

    def __str__(self):
        return self.name


class Prerequisite(models.Model):
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="prerequisites")

    def __str__(self):
        return self.description


class Milestone(models.Model):
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    completed_teams = models.ManyToManyField('Team', blank=True, related_name="milestones_completed")

    def __str__(self):
        return self.description


class TeamImage(CommonImage):
    pass


class Team(models.Model):
    name = models.CharField(max_length=60, null=True, blank=True)
    avatar = models.ForeignKey(TeamImage, on_delete=models.CASCADE, null=True, blank=True, related_name="team")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="teams", null=True)
    members = models.ManyToManyField(Subscriber, related_name="teams")

    def __str__(self):
        return self.name

