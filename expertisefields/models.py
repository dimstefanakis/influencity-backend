from django.db import models
from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from django.core.mail import mail_admins, send_mail
from common.models import CommonImage


# TODO
# add default other option
class ExpertiseField(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return str(self.name)


class ExpertiseFieldMultiple(models.Model):
    name = models.CharField(max_length=100)
    coach = models.ForeignKey(
        'instructor.Coach', on_delete=models.CASCADE, null=True, blank=True, related_name="expertise_fields")

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

    def get_admin_url(self):
        content_type = ContentType.objects.get_for_model(self.__class__)
        return reverse("admin:%s_%s_change" % (content_type.app_label, content_type.model), args=(self.id,))

    def __str__(self):
        return str(self.name)


@receiver(post_save, sender=ExpertiseFieldSuggestion)
def send_mail_to_admins_about_new_expertise_field_suggestion(sender, instance, created, **kwargs):
    if created:
        mail_admins(
            f"New expertise field {instance.name}",
            f"Accept or deny this mentor application here https://api.troosh.app{instance.get_admin_url()}",
            fail_silently=False,
        )
