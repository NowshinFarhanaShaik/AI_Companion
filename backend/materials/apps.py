from django.apps import AppConfig


class MaterialsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "materials"

    def ready(self):
        from materials import handlers, pipeline  # noqa: F401
