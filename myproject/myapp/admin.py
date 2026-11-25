from django.contrib import admin
from .models import JobPost, JobUpdate, UserProfile, SavedJob, PasswordResetOTP, UserNotification, NewsletterSubscriber

admin.site.register(JobPost)
admin.site.register(JobUpdate)
admin.site.register(UserProfile)
admin.site.register(SavedJob)
admin.site.register(PasswordResetOTP)
admin.site.register(UserNotification)
admin.site.register(NewsletterSubscriber)