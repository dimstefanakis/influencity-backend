from django.db import models
from instructor.models import Coach
import uuid

# Create your models here.
class Question(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    answered_by = models.ForeignKey(
        Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="questions_answered")
    body = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.body


class QuestionInvitation(models.Model):
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated = models.DateTimeField(auto_now=True, null=True, blank=True)
    question = models.ForeignKey(Question, blank=True, null=True, on_delete=models.CASCADE, related_name="invitations")
    coach = models.ForeignKey(Coach, blank=True, null=True, on_delete=models.CASCADE, related_name="invitations")
