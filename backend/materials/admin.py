from django.contrib import admin

from materials.models import Concept, Material


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "page_count", "created_at")
    list_filter = ("status",)


admin.site.register(Concept)
