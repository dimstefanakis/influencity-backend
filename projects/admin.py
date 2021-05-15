from django.contrib import admin
from .models import (
    Project, 
    Milestone, 
    Prerequisite, 
    Team, 
    MilestoneCompletionReport, 
    MilestoneCompletionImage, 
    MilestoneCompletionVideo, 
    MilestoneCompletionPlaybackId, 
    MilestoneCompletionVideoAssetMetaData, 
    Coupon
)


class TeamAdmin(admin.ModelAdmin):
    model = Team
    filter_horizontal = ('members',)


class ProjectAdmin(admin.ModelAdmin):
    model = Project
    filter_horizontal = ('members',)


class MilestoneAdmin(admin.ModelAdmin):
    model = Milestone
    filter_horizontal = ('completed_teams',)


class MilestoneCompletionReportAdmin(admin.ModelAdmin):
    model = MilestoneCompletionReport
    filter_horizontal = ('members',)


admin.site.register(Project, ProjectAdmin)
admin.site.register(Milestone, MilestoneAdmin)
admin.site.register(MilestoneCompletionImage)
admin.site.register(Prerequisite)
admin.site.register(Team, TeamAdmin)
admin.site.register(MilestoneCompletionReport, MilestoneCompletionReportAdmin)
admin.site.register(MilestoneCompletionVideo)
admin.site.register(MilestoneCompletionPlaybackId)
admin.site.register(MilestoneCompletionVideoAssetMetaData)
admin.site.register(Coupon)
