from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CommunicationsConfig(AppConfig):
    name = "apps.communications"
    verbose_name = _("Communications")
