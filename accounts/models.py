from django.db import models
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver
from allauth.account.signals import user_signed_up
import uuid


class User(AbstractUser):
    class Meta:
        swappable = "AUTH_USER_MODEL"
        db_table = "auth_user"

    username = models.CharField(blank=False, null=False, max_length=30, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    is_coach = models.BooleanField(default=False)
    is_subscriber = models.BooleanField(default=False)
    surrogate = models.UUIDField(default=uuid.uuid4, db_index=True, unique=True)


@receiver(user_signed_up)
def user_signed_up_(request, user, **kwargs):
    user.is_subscriber = True
    user.save()
