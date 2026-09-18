from django.contrib import admin

from events.models import Job, LearningEvent


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "type", "status", "attempts", "run_after", "last_error")
    list_filter = ("status", "type")


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "type", "user", "project")
    list_filter = ("type",)
