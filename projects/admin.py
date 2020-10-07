from django.contrib import admin
from .models import Project, ProgressLevel, Prerequisite, Team


admin.site.register(Project)
admin.site.register(ProgressLevel)
admin.site.register(Prerequisite)
admin.site.register(Team)
