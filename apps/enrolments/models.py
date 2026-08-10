"""Inscriptions et reconduction.

La reconduction est le workflow central de l'Unipop : les fidèles se réinscrivent
de trimestre en trimestre. Welante n'en gardait qu'une trace indirecte — un statut
« Copié » posé à la main par le secrétariat, qui recopiait chaque inscription une
à une. Moléson en fait une relation explicite (`renewed_from`) : on sait de quelle
inscription chaque reconduction descend, et la chaîne se remonte sur plusieurs
années.
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.contacts.models import DiscountSource
from apps.enrolments.pricing import PriceBreakdown, compute_price


class EnrolmentStatus(models.TextChoices):
    """Cycle de vie d'une inscription.

    `PROPOSED` couvre la reconduction en attente de confirmation : c'est l'état
    dans lequel le participant reçoit « votre cours continue, confirmez en un
    clic ». Il remplace le statut « Copié » de Welante, qui ne disait pas si la
    personne avait accepté.
    """

    DRAFT = "draft", _("Brouillon")
    PROPOSED = "proposed", _("Proposée")
    CONFIRMED = "confirmed", _("Confirmée")
    WAITLISTED = "waitlisted", _("Liste d'attente")
    DECLINED = "declined", _("Déclinée")
    CANCELLED = "cancelled", _("Annulée")


class EnrolmentSource(models.TextChoices):
    """Origine de l'inscription.

    Welante gérait un référentiel « Sources d'inscriptions » ; dans une
    architecture API-first, la source se déduit du consommateur qui écrit.
    """

    ADMIN = "admin", _("Secrétariat")
    WEB = "web", _("Site web")
    PARTICIPANT = "participant", _("Portail participant")
    TRAINER = "trainer", _("Portail formateurs")
    RENEWAL = "renewal", _("Reconduction")
    IMPORT = "import", _("Migration Welante")


class EnrolmentQuerySet(models.QuerySet):
    def active(self):
        """Inscriptions qui occupent une place."""
        return self.filter(status__in=[EnrolmentStatus.CONFIRMED, EnrolmentStatus.PROPOSED])

    def confirmed(self):
        return self.filter(status=EnrolmentStatus.CONFIRMED)

    def awaiting_confirmation(self):
        return self.filter(status=EnrolmentStatus.PROPOSED)


class Enrolment(models.Model):
    """Inscription d'un contact à un cours."""

    course = models.ForeignKey(
        "catalog.Course",
        verbose_name=_("cours"),
        related_name="enrolments",
        on_delete=models.PROTECT,
    )
    participant = models.ForeignKey(
        "contacts.Contact",
        verbose_name=_("participant"),
        related_name="enrolments",
        on_delete=models.PROTECT,
    )
    billing_contact = models.ForeignKey(
        "contacts.Contact",
        verbose_name=_("contact de facturation"),
        related_name="billed_enrolments",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text=_(
            "Employeur, proche ou institution qui règle la facture. "
            "Vide : le participant est facturé lui-même."
        ),
    )

    status = models.CharField(
        _("statut"), max_length=20, choices=EnrolmentStatus, default=EnrolmentStatus.DRAFT
    )
    source = models.CharField(
        _("source"), max_length=20, choices=EnrolmentSource, default=EnrolmentSource.ADMIN
    )

    price_override = models.DecimalField(
        _("prix imposé (CHF)"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Remplace le prix calculé, rabais compris."),
    )
    discount_override = models.DecimalField(
        _("rabais accordé (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Promotion ou geste commercial. Prime sur le rabais automatique."),
    )

    renewed_from = models.OneToOneField(
        "self",
        verbose_name=_("reconduction de"),
        related_name="renewed_to",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    enrolled_on = models.DateField(_("date d'inscription"), default=date.today)
    confirmed_at = models.DateTimeField(_("confirmée le"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("annulée le"), null=True, blank=True)
    cancellation_reason = models.CharField(_("motif"), max_length=200, blank=True)

    notes = models.TextField(_("remarques"), blank=True)
    legacy_reference = models.CharField(
        _("référence Welante"), max_length=50, blank=True, db_index=True
    )

    created_at = models.DateTimeField(_("créée le"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("modifiée le"), auto_now=True)

    objects = EnrolmentQuerySet.as_manager()

    class Meta:
        verbose_name = _("inscription")
        verbose_name_plural = _("inscriptions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["course", "status"], name="inscription_cours_statut"),
            models.Index(fields=["participant", "status"], name="inscription_contact_statut"),
        ]
        constraints = [
            # Une même personne ne s'inscrit qu'une fois à un cours donné.
            models.UniqueConstraint(
                fields=["course", "participant"], name="inscription_unique_par_cours"
            ),
            models.CheckConstraint(
                name="rabais_inscription_entre_0_et_100",
                condition=Q(discount_override__isnull=True)
                | (Q(discount_override__gte=0) & Q(discount_override__lte=100)),
            ),
            models.CheckConstraint(
                name="prix_impose_positif",
                condition=Q(price_override__isnull=True) | Q(price_override__gte=0),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.participant} — {self.course.code}"

    # --- Facturation -------------------------------------------------------

    @property
    def invoiced_contact(self):
        """Contact à facturer — le payeur désigné, sinon le participant."""
        return self.billing_contact or self.participant

    def price_breakdown(self, on: date | None = None) -> PriceBreakdown:
        """Détail du prix de cette inscription.

        Le rabais suit le **participant**, pas le payeur : c'est la personne qui
        suit le cours dont l'adhésion ouvre droit à la réduction, même lorsqu'un
        employeur règle la facture.
        """
        remise = self.participant.best_discount(on or self.enrolled_on)
        return compute_price(
            base_price=self.course.base_price,
            is_intensive=self.course.is_intensive,
            contact_discount_percent=remise.percent,
            contact_discount_label=remise.label,
            price_override=self.price_override,
            discount_override=self.discount_override,
        )

    @property
    def price(self) -> Decimal:
        return self.price_breakdown().final_price

    @property
    def discount_source(self) -> str:
        if self.price_override is not None:
            return DiscountSource.MANUAL
        if self.discount_override is not None:
            return DiscountSource.MANUAL
        if self.course.is_intensive:
            return DiscountSource.NONE
        return self.participant.best_discount(self.enrolled_on).source

    # --- Transitions -------------------------------------------------------

    def confirm(self, *, save: bool = True) -> None:
        self.status = EnrolmentStatus.CONFIRMED
        self.confirmed_at = timezone.now()
        self.cancelled_at = None
        self.cancellation_reason = ""
        if save:
            self.save(
                update_fields=["status", "confirmed_at", "cancelled_at", "cancellation_reason"]
            )

    def cancel(self, reason: str = "", *, save: bool = True) -> None:
        self.status = EnrolmentStatus.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        if save:
            self.save(update_fields=["status", "cancelled_at", "cancellation_reason"])

    def renew_to(self, course, *, source: str = EnrolmentSource.RENEWAL) -> "Enrolment":
        """Propose la même inscription sur un cours de la période suivante.

        Crée une inscription **proposée** : la place n'est acquise qu'après
        confirmation du participant. Les surcharges tarifaires ne sont pas
        reportées — une promotion consentie un trimestre n'engage pas le suivant.
        """
        return Enrolment.objects.create(
            course=course,
            participant=self.participant,
            billing_contact=self.billing_contact,
            status=EnrolmentStatus.PROPOSED,
            source=source,
            renewed_from=self,
        )
