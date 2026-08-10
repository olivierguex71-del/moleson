"""Administration des inscriptions."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.enrolments.models import Enrolment


@admin.register(Enrolment)
class EnrolmentAdmin(ModelAdmin):
    list_display = [
        "participant",
        "course",
        "status",
        "prix_affiche",
        "billing_contact",
        "source",
    ]
    list_filter = ["status", "source", "course__region", "course__period"]
    search_fields = [
        "participant__last_name",
        "participant__first_name",
        "participant__email",
        "course__code",
        "course__title_fr",
    ]
    autocomplete_fields = ["course", "participant", "billing_contact", "renewed_from"]
    readonly_fields = ["detail_du_prix", "confirmed_at", "cancelled_at"]
    fieldsets = [
        (None, {"fields": ["course", "participant", "status", "source"]}),
        (
            _("Facturation"),
            {
                "fields": [
                    "billing_contact",
                    ("price_override", "discount_override"),
                    "detail_du_prix",
                ]
            },
        ),
        (_("Reconduction"), {"fields": ["renewed_from"]}),
        (
            _("Suivi"),
            {
                "fields": [
                    "enrolled_on",
                    "confirmed_at",
                    "cancelled_at",
                    "cancellation_reason",
                    "notes",
                ]
            },
        ),
        (_("Reprise Welante"), {"classes": ["collapse"], "fields": ["legacy_reference"]}),
    ]

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("course", "participant", "billing_contact")
        )

    @admin.display(description=_("prix"))
    def prix_affiche(self, obj: Enrolment) -> str:
        return f"{obj.price:.2f} CHF"

    @admin.display(description=_("détail du prix"))
    def detail_du_prix(self, obj: Enrolment) -> str:
        """Explique le montant au secrétariat, qui doit pouvoir le justifier."""
        if not obj.pk:
            return "—"
        detail = obj.price_breakdown()
        if not detail.has_discount:
            return f"{detail.final_price:.2f} CHF — {detail.explanation}"
        return (
            f"{detail.base_price:.2f} CHF − {detail.discount_percent:.0f} % "
            f"({detail.discount_amount:.2f} CHF) = {detail.final_price:.2f} CHF "
            f"— {detail.explanation}"
        )
