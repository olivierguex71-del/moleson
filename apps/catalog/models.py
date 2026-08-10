"""Catalogue : régions, périodes, matières, lieux, cours et séances.

Trois notions que Welante mélangeait dans un même champ « catégories » sont ici
séparées, parce qu'elles ne servent pas au même usage et ne changent pas au même
rythme :

- la **taxonomie** (matières) structure la navigation du site public ;
- les **étiquettes** (newsletter, coup de cœur, démarrage garanti) relèvent du
  marketing d'une saison ;
- le **type administratif** (ORS, formation interne, cours d'entreprise) commande
  la facturation et les statistiques.

Les mêler obligeait le secrétariat à cocher « Newsletter » dans la même liste que
« Cours de langues > Italien », et rendait tout filtrage fiable impossible.
"""

from datetime import date

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields.ranges import RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Func, Q, Value
from django.utils.translation import gettext_lazy as _

from apps.catalog.course_codes import build_course_code, parse_course_code
from apps.core.models import SwissAddressMixin, TimeStampedModel, TranslatedFieldsMixin


class Region(TranslatedFieldsMixin, TimeStampedModel):
    """District desservi par l'Unipop.

    Entité de premier ordre et non simple attribut : la région structure la
    navigation du site public et forme le suffixe du code de cours.
    """

    code = models.CharField(_("code"), max_length=2, unique=True)
    slug = models.SlugField(_("identifiant d'URL"), max_length=40, unique=True)
    name_fr = models.CharField(_("nom (FR)"), max_length=80)
    name_de = models.CharField(_("nom (DE)"), max_length=80, blank=True)
    main_city = models.CharField(_("ville principale"), max_length=80, blank=True)
    position = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        verbose_name = _("région")
        verbose_name_plural = _("régions")
        ordering = ["position", "code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.tr('name')}"


class PeriodKind(models.TextChoices):
    T1 = "T1", _("1er trimestre")
    T2 = "T2", _("2e trimestre")
    T3 = "T3", _("3e trimestre")
    T4 = "T4", _("4e trimestre")
    S1 = "S1", _("1er semestre")
    S2 = "S2", _("2e semestre")


class Period(TimeStampedModel):
    """Trimestre ou semestre de programmation.

    Les dates de début et de fin ordonnent les périodes chronologiquement, ce qui
    permet de désigner sans ambiguïté « la période suivante » — pivot du workflow
    de reconduction. Un tri alphabétique sur le code placerait S1 avant T4 et
    reconduirait les inscriptions dans le passé.
    """

    year = models.PositiveSmallIntegerField(_("année"))
    kind = models.CharField(_("période"), max_length=2, choices=PeriodKind)
    starts_on = models.DateField(_("début"))
    ends_on = models.DateField(_("fin"))
    is_open_for_enrolment = models.BooleanField(_("inscriptions ouvertes"), default=False)

    class Meta:
        verbose_name = _("période")
        verbose_name_plural = _("périodes")
        ordering = ["-starts_on"]
        constraints = [
            models.UniqueConstraint(fields=["year", "kind"], name="periode_unique_par_annee"),
            models.CheckConstraint(
                name="periode_finit_apres_son_debut",
                condition=Q(ends_on__gt=F("starts_on")),
            ),
        ]

    def __str__(self) -> str:
        return self.code

    @property
    def code(self) -> str:
        """Forme utilisée dans le code de cours, par exemple « 2026-T4 »."""
        return f"{self.year}-{self.kind}"

    def next_period(self):
        """Période suivante dans l'ordre chronologique, ou `None`."""
        return Period.objects.filter(starts_on__gt=self.starts_on).order_by("starts_on").first()

    def contains(self, day: date) -> bool:
        return self.starts_on <= day <= self.ends_on


class Subject(TranslatedFieldsMixin, TimeStampedModel):
    """Matière du catalogue, sur deux niveaux (« Cours de langues > Italien »).

    Le `slug` reprend le Web-Code de Welante : c'est l'identifiant public des
    pages du site, et le conserver évite de casser les URL existantes et leur
    référencement.
    """

    slug = models.SlugField(_("Web-Code"), max_length=60, unique=True)
    name_fr = models.CharField(_("nom (FR)"), max_length=120)
    name_de = models.CharField(_("nom (DE)"), max_length=120, blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("matière parente"),
        related_name="children",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    position = models.PositiveSmallIntegerField(_("ordre"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("matière")
        verbose_name_plural = _("matières")
        ordering = ["position", "name_fr"]

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.tr('name')} > {self.tr('name')}"
        return self.tr("name")

    def clean(self):
        super().clean()
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": _("Une matière ne peut pas être sa propre parente.")}
                )
            if self.parent.parent_id:
                raise ValidationError(
                    {
                        "parent": _(
                            "La taxonomie est limitée à deux niveaux : « %(parent)s » est "
                            "déjà une sous-matière."
                        )
                        % {"parent": self.parent}
                    }
                )


class Location(SwissAddressMixin, TimeStampedModel):
    """Lieu de cours : école, centre sportif, locaux de l'Unipop.

    Référentiel unique, partagé par le catalogue et les futures réservations —
    Welante en tenait deux listes séparées, qui divergeaient.
    """

    name = models.CharField(_("nom"), max_length=150)
    region = models.ForeignKey(
        Region,
        verbose_name=_("région"),
        related_name="locations",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    access_notes_fr = models.TextField(_("accès (FR)"), blank=True)
    access_notes_de = models.TextField(_("accès (DE)"), blank=True)
    is_active = models.BooleanField(_("actif"), default=True)

    class Meta:
        verbose_name = _("lieu")
        verbose_name_plural = _("lieux")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Room(TimeStampedModel):
    """Salle d'un lieu.

    Distinguer la salle du lieu n'est pas un raffinement : une même facture
    mentionne plusieurs salles pour un seul cours, et c'est la salle — non le
    bâtiment — qui ne peut accueillir deux séances à la même heure.
    """

    location = models.ForeignKey(
        Location, verbose_name=_("lieu"), related_name="rooms", on_delete=models.CASCADE
    )
    name = models.CharField(_("salle"), max_length=100)
    capacity = models.PositiveSmallIntegerField(_("capacité"), null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("salle")
        verbose_name_plural = _("salles")
        ordering = ["location__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["location", "name"], name="salle_unique_par_lieu")
        ]

    def __str__(self) -> str:
        return f"{self.location.name} — {self.name}"


class Holiday(TranslatedFieldsMixin, TimeStampedModel):
    """Jour férié, cantonal ou propre à une région.

    Sert à la génération des séances récurrentes : une date fériée est proposée
    à l'exclusion plutôt que créée puis annulée une à une.
    """

    day = models.DateField(_("date"))
    name_fr = models.CharField(_("nom (FR)"), max_length=120)
    name_de = models.CharField(_("nom (DE)"), max_length=120, blank=True)
    region = models.ForeignKey(
        Region,
        verbose_name=_("région"),
        related_name="holidays",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text=_("Vide : férié dans tout le canton."),
    )

    class Meta:
        verbose_name = _("jour férié")
        verbose_name_plural = _("jours fériés")
        ordering = ["day"]
        constraints = [
            models.UniqueConstraint(fields=["day", "region"], name="ferie_unique_par_region"),
        ]

    def __str__(self) -> str:
        return f"{self.day:%d.%m.%Y} — {self.tr('name')}"


class AdministrativeType(models.TextChoices):
    """Régime administratif du cours — distinct de la matière et des étiquettes."""

    STANDARD = "standard", _("Cours au programme")
    ORS = "ors", _("ORS (intégration)")
    INTERNAL = "internal", _("Formation interne")
    CORPORATE = "corporate", _("Cours privés et entreprises")


class CourseStatus(models.TextChoices):
    DRAFT = "draft", _("Brouillon")
    PUBLISHED = "published", _("Publié")
    CANCELLED = "cancelled", _("Annulé")
    COMPLETED = "completed", _("Terminé")


class CourseQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=CourseStatus.PUBLISHED)

    def for_region(self, code: str):
        return self.filter(region__code=code)


class Course(TranslatedFieldsMixin, TimeStampedModel):
    """Un cours d'une période donnée, dans une région donnée."""

    code = models.CharField(
        _("code"),
        max_length=40,
        unique=True,
        help_text=_("Format : AAAA-Px-NNNNNN[v]-RG. Les codes hérités sont acceptés."),
    )
    period = models.ForeignKey(
        Period, verbose_name=_("période"), related_name="courses", on_delete=models.PROTECT
    )
    region = models.ForeignKey(
        Region, verbose_name=_("région"), related_name="courses", on_delete=models.PROTECT
    )

    # 400 et non 200 : l'export Welante contient des titres de 359 caractères,
    # titre et sous-titre confondus dans le même champ. Tronquer perdrait du
    # contenu ; la longueur excessive est signalée à l'import, pour nettoyage.
    title_fr = models.CharField(_("titre (FR)"), max_length=400)
    title_de = models.CharField(_("titre (DE)"), max_length=400, blank=True)
    summary_fr = models.TextField(_("accroche (FR)"), blank=True)
    summary_de = models.TextField(_("accroche (DE)"), blank=True)
    description_fr = models.TextField(_("descriptif (FR)"), blank=True)
    description_de = models.TextField(_("descriptif (DE)"), blank=True)

    subjects = models.ManyToManyField(
        Subject, verbose_name=_("matières"), related_name="courses", blank=True
    )
    trainers = models.ManyToManyField(
        "contacts.Trainer", verbose_name=_("formateurs"), related_name="courses", blank=True
    )
    default_room = models.ForeignKey(
        Room,
        verbose_name=_("salle habituelle"),
        related_name="courses",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    base_price = models.DecimalField(
        _("prix de base (CHF)"),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    is_intensive = models.BooleanField(
        _("cours intensif"),
        default=False,
        help_text=_("Neutralise tous les rabais membres et collaborateurs."),
    )

    min_participants = models.PositiveSmallIntegerField(_("minimum"), null=True, blank=True)
    max_participants = models.PositiveSmallIntegerField(_("maximum"), null=True, blank=True)

    administrative_type = models.CharField(
        _("type administratif"),
        max_length=20,
        choices=AdministrativeType,
        default=AdministrativeType.STANDARD,
    )
    status = models.CharField(
        _("statut"), max_length=20, choices=CourseStatus, default=CourseStatus.DRAFT
    )

    # Étiquettes marketing — volontairement séparées de la taxonomie.
    in_newsletter = models.BooleanField(_("dans la newsletter"), default=False)
    is_highlight = models.BooleanField(_("coup de cœur"), default=False)
    has_guaranteed_start = models.BooleanField(_("démarrage garanti"), default=False)
    is_on_demand = models.BooleanField(_("sur demande"), default=False)

    continues = models.ForeignKey(
        "self",
        verbose_name=_("suite du cours"),
        related_name="continued_by",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_(
            "Cours de la période précédente dont celui-ci prend la suite. "
            "C'est ce lien qui permet de proposer la reconduction aux inscrits."
        ),
    )

    legacy_reference = models.CharField(
        _("référence Welante"), max_length=50, blank=True, db_index=True
    )

    objects = CourseQuerySet.as_manager()

    class Meta:
        verbose_name = _("cours")
        verbose_name_plural = _("cours")
        ordering = ["-period__starts_on", "code"]
        indexes = [
            models.Index(fields=["status", "region"], name="cours_statut_region"),
        ]
        constraints = [
            models.CheckConstraint(
                name="cours_maximum_superieur_au_minimum",
                condition=Q(min_participants__isnull=True)
                | Q(max_participants__isnull=True)
                | Q(max_participants__gte=F("min_participants")),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.tr('title')}"

    @property
    def canonical_code(self) -> str | None:
        """Code que ce cours porterait selon la convention, ou `None` si indécidable."""
        parts = parse_course_code(self.code)
        if not parts:
            return None
        return build_course_code(
            year=self.period.year,
            period=self.period.kind,
            number=parts.number,
            variant=parts.variant,
            region=self.region.code,
        )

    def clean(self):
        super().clean()
        # Un code canonique doit s'accorder avec la période et la région saisies.
        # Les codes hérités échappent au contrôle : ils suivent d'autres formes,
        # sans que cela révèle une erreur.
        parts = parse_course_code(self.code)
        if not parts or not (self.period_id and self.region_id):
            return
        erreurs = {}
        if parts.region != self.region.code:
            erreurs["code"] = _(
                "Le suffixe « %(suffixe)s » désigne une autre région que « %(region)s »."
            ) % {"suffixe": parts.region, "region": self.region.code}
        elif (parts.year, parts.period) != (self.period.year, self.period.kind):
            erreurs["code"] = _(
                "Le code annonce la période %(code)s, le cours est rattaché à %(periode)s."
            ) % {"code": f"{parts.year}-{parts.period}", "periode": self.period.code}
        if erreurs:
            raise ValidationError(erreurs)


class SessionStatus(models.TextChoices):
    SCHEDULED = "scheduled", _("Prévue")
    CANCELLED = "cancelled", _("Annulée")


class CourseSession(TimeStampedModel):
    """Une séance : sa date, son horaire, sa salle.

    L'horaire vit sur la séance et non sur le cours, parce qu'il varie
    réellement au sein d'un même cours — une facture montre « 2× mardi 15h45,
    4× jeudi 16h00, 1× mardi 16h00 ». Les documents (confirmations, factures)
    puisent donc dans les séances, jamais dans un horaire résumé au niveau cours.
    """

    course = models.ForeignKey(
        Course, verbose_name=_("cours"), related_name="sessions", on_delete=models.CASCADE
    )
    starts_at = models.DateTimeField(_("début"))
    ends_at = models.DateTimeField(_("fin"))
    room = models.ForeignKey(
        Room,
        verbose_name=_("salle"),
        related_name="sessions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        _("statut"), max_length=20, choices=SessionStatus, default=SessionStatus.SCHEDULED
    )
    cancellation_reason = models.CharField(_("motif d'annulation"), max_length=200, blank=True)
    note_fr = models.CharField(_("remarque (FR)"), max_length=200, blank=True)
    note_de = models.CharField(_("remarque (DE)"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("séance")
        verbose_name_plural = _("séances")
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["course", "starts_at"], name="seance_cours_debut")]
        constraints = [
            models.CheckConstraint(
                name="seance_finit_apres_son_debut",
                condition=Q(ends_at__gt=F("starts_at")),
            ),
            # Une salle ne peut accueillir deux séances au même moment. Les
            # séances annulées sont exclues : elles libèrent la salle.
            ExclusionConstraint(
                name="salle_sans_double_reservation",
                expressions=[
                    (F("room"), RangeOperators.EQUAL),
                    (
                        Func(
                            F("starts_at"),
                            F("ends_at"),
                            Value("[)"),
                            function="tstzrange",
                            output_field=DateTimeRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(status=SessionStatus.SCHEDULED, room__isnull=False),
                violation_error_message=_("Cette salle est déjà occupée sur ce créneau."),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course.code} — {self.starts_at:%d.%m.%Y %H:%M}"

    @property
    def is_cancelled(self) -> bool:
        return self.status == SessionStatus.CANCELLED
