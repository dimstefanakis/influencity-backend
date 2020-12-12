from django.contrib import admin
from .models import Tier, Benefit


class TierAdmin(admin.ModelAdmin):
    model = Tier
    filter_horizontal = ('subscribers',)


admin.site.register(Tier, TierAdmin)
admin.site.register(Benefit)
