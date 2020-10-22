from django.contrib import admin
from .models import Coach, CoachAvatar


class CoachAdmin(admin.ModelAdmin):
    model = Coach
    filter_horizontal = ('subscribers',)


admin.site.register(Coach, CoachAdmin)
admin.site.register(CoachAvatar)
