import os
from django.contrib.sites.models import Site
from rest_auth.serializers import PasswordResetSerializer, PasswordResetConfirmSerializer


class CustomPasswordResetSerializer(PasswordResetSerializer):
    def get_email_options(self):
        return {
            'html_email_template_name': 'accounts/'
                                    'password_reset_email.html',
            'extra_email_context': {
                'frontend_url': 'https://%s' % (Site.objects.get_current().domain),
            }
        }
