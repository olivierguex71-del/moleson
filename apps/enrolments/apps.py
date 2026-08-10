from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EnrolmentsConfig(AppConfig):
    name = "apps.enrolments"
    verbose_name = _("Inscriptions")
