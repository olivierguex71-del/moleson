"""Campagnes d'envoi.

Correction directe d'un anti-pattern Welante : l'export des membres ajoute une
**colonne par saison** (« Programmversand Herbst 2019 », « Frühling 2020 »…).
Chaque campagne élargissait donc la table des contacts, et l'historique se
perdait dès qu'une colonne était réutilisée ou supprimée.

Ici une campagne est une ligne, un envoi est une ligne : ajouter une saison ne
touche pas au schéma, et l'on sait qui a reçu quoi, quand, et dans quelle langue.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel, TranslatedFieldsMixin


class CampaignChannel(models.TextChoices):
    EMAIL = "email", _("Courriel")
    POSTAL = "postal", _("Courrier postal")


class MailingCampaign(TranslatedFieldsMixin, TimeStampedModel):
    """Un envoi groupé : programme de saison, newsletter, information."""

    slug = models.SlugField(_("identifiant"), max_length=80, unique=True)
    name_fr = models.CharField(_("nom (FR)"), max_length=150)
    name_de = models.CharField(_("nom (DE)"), max_length=150, blank=True)
    channel = models.CharField(
        _("canal"), max_length=20, choices=CampaignChannel, default=CampaignChannel.EMAIL
    )
    period = models.ForeignKey(
        "catalog.Period",
        verbose_name=_("période"),
        related_name="campaigns",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    scheduled_for = models.DateField(_("prévu le"), null=True, blank=True)
    sent_at = models.DateTimeField(_("envoyé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("campagne")
        verbose_name_plural = _("campagnes")
        ordering = ["-scheduled_for", "-created_at"]

    def __str__(self) -> str:
        return self.tr("name")


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", _("À envoyer")
    SENT = "sent", _("Envoyé")
    FAILED = "failed", _("Échec")
    SKIPPED = "skipped", _("Ignoré")


class MailingDelivery(TimeStampedModel):
    """Envoi d'une campagne à un contact.

    La langue est figée au moment de l'envoi : si un contact change plus tard de
    langue de correspondance, l'historique doit continuer de dire dans quelle
    langue le courrier est réellement parti.
    """

    campaign = models.ForeignKey(
        MailingCampaign,
        verbose_name=_("campagne"),
        related_name="deliveries",
        on_delete=models.CASCADE,
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        verbose_name=_("contact"),
        related_name="deliveries",
        on_delete=models.CASCADE,
    )
    language = models.CharField(_("langue d'envoi"), max_length=2)
    status = models.CharField(
        _("statut"), max_length=20, choices=DeliveryStatus, default=DeliveryStatus.PENDING
    )
    sent_at = models.DateTimeField(_("envoyé le"), null=True, blank=True)
    failure_reason = models.CharField(_("motif d'échec"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("envoi")
        verbose_name_plural = _("envois")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "contact"], name="un_envoi_par_contact_et_campagne"
            )
        ]

    def __str__(self) -> str:
        return f"{self.campaign} → {self.contact}"
