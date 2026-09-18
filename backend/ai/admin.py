from django.contrib import admin

from ai.models import AICallLog, EvalRun


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "feature", "model", "status", "latency_ms", "input_tokens", "output_tokens", "retries")
    list_filter = ("feature", "status", "model")


admin.site.register(EvalRun)
