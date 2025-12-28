from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    verbose_name = 'Følgpris'

    def ready(self):
        """
        Initialize application on startup.

        This method is called when Django starts, making it the perfect
        place to configure structlog for the entire application.
        """
        # Configure structlog for centralized logging
        from config.logging_config import configure_structlog
        configure_structlog()
