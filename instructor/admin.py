from django.contrib import admin
from .models import Coach, CoachAvatar, CoachApplication


class CoachAdmin(admin.ModelAdmin):
    model = Coach
    filter_horizontal = ('subscribers',)


admin.site.register(Coach, CoachAdmin)
admin.site.register(CoachAvatar)
admin.site.register(CoachApplication)
