from django.contrib import admin

from accounts.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_staff", "is_active", "created_at")
    search_fields = ("email", "name")
    exclude = ("password",)
