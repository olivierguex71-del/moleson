"""Contacts, adhésions et formateurs.

Une seule entité **Contact** porte toute personne connue de l'Unipop. Être
participant, membre ou formateur n'est pas une nature différente mais un rôle,
matérialisé par une inscription, une adhésion ou un profil de formateur. Welante
séparait « Contacts » et « Participant-e-s », ce qui fabriquait des doublons
structurels : la même personne existait deux fois dès qu'elle changeait de rôle.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField
from django.contrib.postgres.fields.ranges import RangeOperators
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Func, Q, Value
from django.db.models.functions import Greatest
from django.utils.translation import gettext_lazy as _

from apps.core.fields import EncryptedTextField
from apps.core.models import (
    SwissAddressMixin,
    TimeStampedModel,
    TranslatedFieldsMixin,
    content_language,
)
from apps.core.validators import format_iban, normalize_iban, validate_iban


class Salutation(models.TextChoices):
    """Civilité déclarée, base de la formule d'appel.

    Donnée fournie par la personne, jamais déduite de son prénom. `NEUTRAL` sert
    aux personnes qui ne souhaitent pas de civilité genrée et aux organisations.
    """

    MADAM = "madam", _("Madame")
    SIR = "sir", _("Monsieur")
    NEUTRAL = "neutral", _("Sans civilité")


#: Formules d'appel par civilité et par langue de correspondance.
#: Welante stockait la formule en texte dans une colonne — donc figée à la saisie
#: et fausse dès qu'un nom changeait. Ici elle se calcule.
_FORMULES = {
    ("madam", "fr"): "Madame {last_name}",
    ("sir", "fr"): "Monsieur {last_name}",
    ("neutral", "fr"): "Bonjour {first_name} {last_name}",
    ("madam", "de"): "Sehr geehrte Frau {last_name}",
    ("sir", "de"): "Sehr geehrter Herr {last_name}",
    ("neutral", "de"): "Guten Tag {first_name} {last_name}",
}


#: Rabais des collaborateurs de l'Unipop. C'est un rôle, pas un type d'adhésion :
#: il ne figure donc pas dans `MembershipType` et ne se cumule pas avec lui.
COLLABORATOR_DISCOUNT = Decimal("10")


class DiscountSource(models.TextChoices):
    """D'où vient un rabais — pour pouvoir l'expliquer sur une facture."""

    NONE = "none", _("Aucun rabais")
    MEMBERSHIP = "membership", _("Adhésion")
    COLLABORATOR = "collaborator", _("Collaborateur/trice")
    MANUAL = "manual", _("Rabais accordé manuellement")


@dataclass(frozen=True)
class Discount:
    """Un taux de rabais et sa justification."""

    percent: Decimal
    source: str
    label: str


class ContactQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def reachable_by_email(self):
        """Contacts joignables par courriel — les seuls éligibles au magic link."""
        return self.exclude(email="")

    def similar_to(self, *, last_name: str, email: str = "", threshold: float = 0.4):
        """Contacts ressemblant à ceux passés en paramètre, les plus proches d'abord.

        Sert à la détection de doublons **au moment de la saisie** : Welante
        proposait un écran de nettoyage a posteriori, quand le doublon avait déjà
        essaimé dans les inscriptions. La similarité par trigrammes rattrape les
        coquilles (« Villars -sur-Glâne ») qu'une égalité stricte laisse passer.
        """
        proximite = TrigramSimilarity("last_name", last_name)
        if email:
            proximite = Greatest(proximite, TrigramSimilarity("email", email))
        return (
            self.annotate(similarity=proximite)
            .filter(similarity__gte=threshold)
            .order_by("-similarity")
        )


class Contact(SwissAddressMixin, TimeStampedModel):
    """Toute personne ou organisation connue de l'Unipop."""

    salutation = models.CharField(
        _("civilité"), max_length=10, choices=Salutation, default=Salutation.NEUTRAL
    )
    first_name = models.CharField(_("prénom"), max_length=100, blank=True)
    last_name = models.CharField(_("nom"), max_length=100, blank=True)
    organisation = models.CharField(_("organisation"), max_length=200, blank=True)

    correspondence_language = models.CharField(
        _("langue de correspondance"),
        max_length=2,
        choices=[(code, code.upper()) for code in settings.CONTENT_LANGUAGES],
        default=settings.LANGUAGE_CODE,
        help_text=_("Toute communication sortante part dans cette langue."),
    )

    email = models.EmailField(_("courriel"), blank=True)
    phone = models.CharField(_("téléphone"), max_length=30, blank=True)
    mobile = models.CharField(_("mobile"), max_length=30, blank=True)
    birth_date = models.DateField(_("date de naissance"), null=True, blank=True)

    is_collaborator = models.BooleanField(
        _("collaborateur/trice"),
        default=False,
        help_text=_("Ouvre droit au rabais collaborateur, sans être un type d'adhésion."),
    )
    is_archived = models.BooleanField(_("archivé"), default=False)

    groups = models.ManyToManyField(
        "contacts.ContactGroup", verbose_name=_("groupes"), related_name="contacts", blank=True
    )

    legacy_notes = models.TextField(
        _("notes historiques (Welante)"),
        blank=True,
        help_text=_(
            "Journal repris de Welante, en lecture seule. Les nouvelles notes "
            "sont horodatées et attribuées à leur auteur."
        ),
    )
    legacy_reference = models.CharField(
        _("référence Welante"), max_length=50, blank=True, db_index=True
    )

    objects = ContactQuerySet.as_manager()

    class Meta:
        verbose_name = _("contact")
        verbose_name_plural = _("contacts")
        ordering = ["last_name", "first_name", "organisation"]
        indexes = [
            # GIN + trigrammes : c'est cet index qui rend la recherche de
            # doublons instantanée au lieu de parcourir toute la table.
            GinIndex(
                name="contact_nom_trigram",
                fields=["last_name"],
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                name="contact_email_trigram",
                fields=["email"],
                opclasses=["gin_trgm_ops"],
            ),
            models.Index(fields=["postal_code"], name="contact_npa"),
        ]
        constraints = [
            models.CheckConstraint(
                name="contact_a_un_nom_ou_une_organisation",
                condition=~Q(last_name="") | ~Q(organisation=""),
                violation_error_message=_(
                    "Un contact doit avoir au moins un nom de famille ou une organisation."
                ),
            )
        ]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        personne = " ".join(part for part in (self.first_name, self.last_name) if part)
        if personne and self.organisation:
            return f"{personne} ({self.organisation})"
        return personne or self.organisation

    @property
    def is_organisation(self) -> bool:
        return bool(self.organisation and not self.last_name)

    def salutation_line(self, language: str | None = None) -> str:
        """Formule d'appel, dans la langue de correspondance du contact."""
        language = content_language(language or self.correspondence_language)
        modele = _FORMULES[(self.salutation, language)]
        return modele.format(first_name=self.first_name, last_name=self.last_name).strip()

    def active_membership(self, on: date | None = None):
        """Adhésion en vigueur à une date donnée, ou `None`."""
        on = on or date.today()
        return (
            self.memberships.filter(starts_on__lte=on)
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gt=on))
            .select_related("type")
            .first()
        )

    def best_discount(self, on: date | None = None) -> "Discount":
        """Rabais le plus avantageux auquel le contact a droit, et sa provenance.

        Les rabais ne se cumulent jamais : un membre bienfaiteur (15 %) également
        collaborateur (10 %) obtient 15 %, pas 25 %. Retourner la provenance avec
        le taux permet d'expliquer le prix sur la facture plutôt que d'afficher
        un montant que personne ne sait justifier.
        """
        candidats = [Discount(Decimal("0"), DiscountSource.NONE, "")]
        if self.is_collaborator:
            candidats.append(
                Discount(COLLABORATOR_DISCOUNT, DiscountSource.COLLABORATOR, _("Collaborateur"))
            )
        if adhesion := self.active_membership(on):
            candidats.append(
                Discount(
                    adhesion.type.discount_percent,
                    DiscountSource.MEMBERSHIP,
                    adhesion.type.tr("name"),
                )
            )
        return max(candidats, key=lambda remise: remise.percent)


class ContactGroup(TranslatedFieldsMixin, TimeStampedModel):
    """Segment de contacts, pour le ciblage des communications."""

    slug = models.SlugField(_("identifiant"), max_length=60, unique=True)
    name_fr = models.CharField(_("nom (FR)"), max_length=120)
    name_de = models.CharField(_("nom (DE)"), max_length=120, blank=True)

    class Meta:
        verbose_name = _("groupe de contacts")
        verbose_name_plural = _("groupes de contacts")
        ordering = ["name_fr"]

    def __str__(self) -> str:
        return self.tr("name")


class ContactNote(TimeStampedModel):
    """Note horodatée et attribuée, en contexte sur la fiche du contact.

    Remplace le champ « Notes » de Welante, devenu un journal de dix ans en texte
    concaténé où l'on ne savait plus ni qui avait écrit quoi, ni quand.
    """

    contact = models.ForeignKey(
        Contact, verbose_name=_("contact"), related_name="notes", on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("auteur"),
        related_name="contact_notes",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    body = models.TextField(_("note"))

    class Meta:
        verbose_name = _("note")
        verbose_name_plural = _("notes")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.contact} — {self.created_at:%d.%m.%Y}"


class MembershipType(TranslatedFieldsMixin, TimeStampedModel):
    """Type d'adhésion et rabais associé.

    Le rabais vit ici plutôt que dans le code : le comité peut le faire évoluer
    sans déploiement, et l'historique des inscriptions reste lisible.
    """

    code = models.SlugField(_("code"), max_length=40, unique=True)
    name_fr = models.CharField(_("nom (FR)"), max_length=120)
    name_de = models.CharField(_("nom (DE)"), max_length=120, blank=True)
    discount_percent = models.DecimalField(
        _("rabais (%)"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Appliqué au prix de base, sauf sur les cours intensifs."),
    )
    annual_fee = models.DecimalField(
        _("cotisation annuelle (CHF)"), max_digits=8, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("type d'adhésion")
        verbose_name_plural = _("types d'adhésion")
        ordering = ["discount_percent", "code"]
        constraints = [
            models.CheckConstraint(
                name="rabais_entre_0_et_100",
                condition=Q(discount_percent__gte=0) & Q(discount_percent__lte=100),
            )
        ]

    def __str__(self) -> str:
        return f"{self.tr('name')} ({self.discount_percent:.0f} %)"


class Membership(TimeStampedModel):
    """Adhésion d'un contact, sur une période donnée."""

    contact = models.ForeignKey(
        Contact, verbose_name=_("contact"), related_name="memberships", on_delete=models.CASCADE
    )
    type = models.ForeignKey(
        MembershipType,
        verbose_name=_("type"),
        related_name="memberships",
        on_delete=models.PROTECT,
    )
    starts_on = models.DateField(_("début"))
    ends_on = models.DateField(
        _("fin"), null=True, blank=True, help_text=_("Vide : adhésion en cours.")
    )

    class Meta:
        verbose_name = _("adhésion")
        verbose_name_plural = _("adhésions")
        ordering = ["-starts_on"]
        constraints = [
            models.CheckConstraint(
                name="adhesion_finit_apres_son_debut",
                condition=Q(ends_on__isnull=True) | Q(ends_on__gt=F("starts_on")),
            ),
            # Deux adhésions simultanées rendraient le rabais applicable ambigu.
            # La règle est posée dans la base, donc vraie quel que soit le chemin
            # d'écriture — administration, API ou script de migration.
            ExclusionConstraint(
                name="adhesions_sans_chevauchement",
                expressions=[
                    (F("contact"), RangeOperators.EQUAL),
                    (
                        Func(
                            F("starts_on"),
                            F("ends_on"),
                            Value("[)"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_message=_("Ce contact a déjà une adhésion couvrant cette période."),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contact} — {self.type}"

    def is_active_on(self, on: date | None = None) -> bool:
        on = on or date.today()
        return self.starts_on <= on and (self.ends_on is None or self.ends_on > on)


class Trainer(TimeStampedModel):
    """Profil de formateur/formatrice greffé sur un contact.

    Les données de paie vivent ici et non sur le contact : elles ne concernent
    qu'une poignée de personnes et relèvent d'un régime d'accès distinct (nLPD).
    """

    contact = models.OneToOneField(
        Contact, verbose_name=_("contact"), related_name="trainer", on_delete=models.PROTECT
    )
    biography_fr = models.TextField(_("présentation (FR)"), blank=True)
    biography_de = models.TextField(_("présentation (DE)"), blank=True)

    iban = models.CharField(_("IBAN"), max_length=34, blank=True, validators=[validate_iban])
    bic = models.CharField(_("BIC"), max_length=11, blank=True)
    bank_name = models.CharField(_("banque"), max_length=120, blank=True)

    ahv_number = EncryptedTextField(
        _("no AVS"),
        blank=True,
        help_text=_(
            "Donnée sensible (nLPD) : chiffrée au repos, réservée au rôle "
            "administration-comptabilité et exclue des exports par défaut."
        ),
    )
    ahv_waiver = models.BooleanField(
        _("renonciation AVS"),
        default=False,
        help_text=_("La personne a renoncé aux cotisations AVS sur ces honoraires."),
    )

    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("formateur/formatrice")
        verbose_name_plural = _("formateurs et formatrices")
        ordering = ["contact__last_name", "contact__first_name"]

    def __str__(self) -> str:
        return str(self.contact)

    @property
    def formatted_iban(self) -> str:
        return format_iban(self.iban)

    def clean(self):
        super().clean()
        # Normaliser avant de valider : les exports Welante mêlent IBAN espacés
        # et collés, et un IBAN comparable est un IBAN compacté.
        self.iban = normalize_iban(self.iban)
        if self.iban:
            try:
                validate_iban(self.iban)
            except ValidationError as exc:
                raise ValidationError({"iban": exc}) from exc

    def save(self, *args, **kwargs):
        self.iban = normalize_iban(self.iban)
        super().save(*args, **kwargs)
