from django.contrib import admin
from .models import Question, QuestionInvitation, QaSession, AvailableTimeRange, CommonQuestion

# Register your models here.
admin.site.register(Question)
admin.site.register(QuestionInvitation)
admin.site.register(QaSession)
admin.site.register(AvailableTimeRange)
admin.site.register(CommonQuestion)
