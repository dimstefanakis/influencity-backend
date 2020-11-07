from django.contrib import admin
from .models import Project, Milestone, Prerequisite, Team


class TeamAdmin(admin.ModelAdmin):
    model = Team
    filter_horizontal = ('members',)


class ProjectAdmin(admin.ModelAdmin):
    model = Project
    filter_horizontal = ('members',)


class MilestoneAdmin(admin.ModelAdmin):
    model = Milestone
    filter_horizontal = ('completed_teams',)


admin.site.register(Project, ProjectAdmin)
admin.site.register(Milestone, MilestoneAdmin)
admin.site.register(Prerequisite)
admin.site.register(Team, TeamAdmin)
