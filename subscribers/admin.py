from django.contrib import admin
from .models import Subscriber, SubscriberAvatar, Subscription

# Register your models here.
admin.site.register(Subscriber)
admin.site.register(SubscriberAvatar)
admin.site.register(Subscription)
