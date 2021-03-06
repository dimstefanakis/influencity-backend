from django.db import models
from subscribers.models import Subscriber
from common.models import CommonImage
from instructor.models import Coach
from accounts.models import User
import uuid


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

    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    coach = models.ForeignKey(Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="created_projects")
    name = models.CharField(max_length=200, blank=False, null=False, default="")
    description = models.TextField(max_length=2000, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField(default=1, blank=False, null=False)
    members = models.ManyToManyField(Subscriber, blank=True, related_name="projects")

    def __str__(self):
        return self.name


class Prerequisite(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="prerequisites")

    def __str__(self):
        return self.description


class Milestone(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    completed_teams = models.ManyToManyField('Team', blank=True, related_name="milestones_completed")

    def __str__(self):
        return self.description


class MilestoneCompletionReport(models.Model):
    PENDING = 'PD'
    ACCEPTED = 'AC'
    REJECTED = 'RJ'
    STATUSES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    ]

    PROCESSING = 'PR'
    DONE = 'DO'
    STATUS_CHOICES = [
        (PROCESSING, 'Processing'),
        (DONE, 'Done')
    ]

    status = models.CharField(
        max_length=2,
        choices=STATUSES,
        default=PENDING,
    )
    
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    video_status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=PROCESSING)
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name="reports", null=True, blank=True)
    members = models.ManyToManyField(Subscriber, related_name="milestone_reports")
    message = models.TextField(null=True, blank=True)


class MilestoneCompletionImage(CommonImage):
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE, null=True,
                                                    blank=True, related_name="images")


class MilestoneCompletionVideoAssetMetaData(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE)


class MilestoneCompletionVideo(models.Model):
    passthrough = models.UUIDField(default=uuid.uuid1)
    milestone_completion_report = models.ForeignKey(MilestoneCompletionReport, on_delete=models.CASCADE, related_name="videos")
    asset_id = models.CharField(max_length=120)


class MilestoneCompletionPlaybackId(models.Model):
    policy = models.CharField(max_length=30)
    playback_id = models.CharField(max_length=100)
    video = models.ForeignKey(MilestoneCompletionVideo, on_delete=models.CASCADE, related_name="playback_ids")


class TeamImage(CommonImage):
    pass


class Team(models.Model):
    name = models.CharField(max_length=60, null=True, blank=True)
    avatar = models.ForeignKey(TeamImage, on_delete=models.CASCADE, null=True, blank=True, related_name="team")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="teams", null=True)
    members = models.ManyToManyField(Subscriber, related_name="teams")

    def __str__(self):
        return self.name

