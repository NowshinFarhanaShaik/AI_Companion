from django.apps import AppConfig


class TutorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tutor"

    def ready(self):
        from tutor import handlers  # noqa: F401
