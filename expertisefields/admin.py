from django.contrib import admin
from .models import ExpertiseField, ExpertiseFieldAvatar, ExpertiseFieldSuggestion

# Register your models here.
admin.site.register(ExpertiseField)
admin.site.register(ExpertiseFieldAvatar)
admin.site.register(ExpertiseFieldSuggestion)
