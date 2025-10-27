from django.apps import AppConfig


class RagConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "parliament.rag"
    verbose_name = "Retrieval and AI Guardrails"
