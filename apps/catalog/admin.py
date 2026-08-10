"""Administration du catalogue."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.catalog.models import (
    Course,
    CourseSession,
    Holiday,
    Location,
    Period,
    Region,
    Room,
    Subject,
)


@admin.register(Region)
class RegionAdmin(ModelAdmin):
    list_display = ["code", "name_fr", "name_de", "main_city", "position"]
    search_fields = ["code", "name_fr", "name_de", "main_city"]


@admin.register(Period)
class PeriodAdmin(ModelAdmin):
    list_display = ["code", "starts_on", "ends_on", "is_open_for_enrolment"]
    list_filter = ["year", "kind", "is_open_for_enrolment"]
    search_fields = ["year"]


@admin.register(Subject)
class SubjectAdmin(ModelAdmin):
    list_display = ["__str__", "slug", "position", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name_fr", "name_de", "slug"]
    autocomplete_fields = ["parent"]


class RoomInline(TabularInline):
    model = Room
    extra = 0
    fields = ["name", "capacity", "is_active"]


@admin.register(Location)
class LocationAdmin(ModelAdmin):
    list_display = ["name", "region", "locality_line", "is_active"]
    list_filter = ["region", "is_active"]
    search_fields = ["name", "city", "street"]
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ["name", "location", "capacity", "is_active"]
    list_filter = ["location", "is_active"]
    search_fields = ["name", "location__name"]


@admin.register(Holiday)
class HolidayAdmin(ModelAdmin):
    list_display = ["day", "name_fr", "name_de", "region"]
    list_filter = ["region"]
    search_fields = ["name_fr", "name_de"]


class CourseSessionInline(TabularInline):
    """Les séances s'éditent dans la fiche du cours, pas dans un écran séparé.

    Welante avait un menu « Jours de cours » distinct : on créait un cours ici,
    puis on allait ailleurs poser ses dates.
    """

    model = CourseSession
    extra = 0
    fields = ["starts_at", "ends_at", "room", "status", "cancellation_reason"]
    ordering = ["starts_at"]


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ["code", "title_fr", "period", "region", "base_price", "status"]
    list_filter = [
        "status",
        "region",
        "period",
        "administrative_type",
        "is_intensive",
        "in_newsletter",
        "is_highlight",
    ]
    search_fields = ["code", "title_fr", "title_de", "legacy_reference"]
    autocomplete_fields = ["period", "region", "subjects", "trainers", "default_room", "continues"]
    inlines = [CourseSessionInline]
    fieldsets = [
        (None, {"fields": ["code", ("period", "region"), "status"]}),
        (
            _("Contenu bilingue"),
            {
                "description": _(
                    "Chaque champ existe en français et en allemand. Ne jamais saisir "
                    "les deux langues dans un même champ."
                ),
                "fields": [
                    ("title_fr", "title_de"),
                    ("summary_fr", "summary_de"),
                    ("description_fr", "description_de"),
                ],
            },
        ),
        (_("Classement"), {"fields": ["subjects", "administrative_type"]}),
        (
            _("Étiquettes"),
            {
                "description": _("Distinctes de la taxonomie : elles relèvent du marketing."),
                "fields": [
                    "in_newsletter",
                    "is_highlight",
                    "has_guaranteed_start",
                    "is_on_demand",
                ],
            },
        ),
        (
            _("Organisation"),
            {
                "fields": [
                    "trainers",
                    "default_room",
                    ("min_participants", "max_participants"),
                ]
            },
        ),
        (_("Tarif"), {"fields": ["base_price", "is_intensive"]}),
        (_("Reconduction"), {"fields": ["continues"]}),
        (_("Reprise Welante"), {"classes": ["collapse"], "fields": ["legacy_reference"]}),
    ]


@admin.register(CourseSession)
class CourseSessionAdmin(ModelAdmin):
    list_display = ["course", "starts_at", "ends_at", "room", "status"]
    list_filter = ["status", "room__location", "course__region"]
    search_fields = ["course__code", "course__title_fr"]
    autocomplete_fields = ["course", "room"]
    date_hierarchy = "starts_at"
