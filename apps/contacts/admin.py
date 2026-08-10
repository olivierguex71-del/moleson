"""Administration des contacts, adhésions et formateurs."""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.contacts.models import (
    Contact,
    ContactGroup,
    ContactNote,
    Membership,
    MembershipType,
    Trainer,
)


class MembershipInline(TabularInline):
    model = Membership
    extra = 0
    fields = ["type", "starts_on", "ends_on"]


class ContactNoteInline(TabularInline):
    model = ContactNote
    extra = 0
    fields = ["body", "author", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Contact)
class ContactAdmin(ModelAdmin):
    list_display = [
        "display_name",
        "correspondence_language",
        "email",
        "locality_line",
        "is_collaborator",
        "is_archived",
    ]
    list_filter = ["correspondence_language", "is_collaborator", "is_archived", "groups"]
    # La recherche porte sur les champs saisis par le secrétariat ; la détection
    # de doublons par similarité vit dans ContactQuerySet.similar_to().
    search_fields = ["last_name", "first_name", "organisation", "email", "city"]
    autocomplete_fields = ["groups"]
    inlines = [MembershipInline, ContactNoteInline]
    fieldsets = [
        (
            _("Identité"),
            {
                "fields": [
                    "salutation",
                    ("first_name", "last_name"),
                    "organisation",
                    "birth_date",
                ]
            },
        ),
        (
            _("Correspondance"),
            {"fields": ["correspondence_language", "email", ("phone", "mobile")]},
        ),
        (
            _("Adresse"),
            {
                "fields": [
                    ("street", "house_number"),
                    "address_complement",
                    ("postal_code", "city"),
                    "country",
                ]
            },
        ),
        (_("Statut"), {"fields": ["is_collaborator", "is_archived", "groups"]}),
        (
            _("Reprise Welante"),
            {"classes": ["collapse"], "fields": ["legacy_reference", "legacy_notes"]},
        ),
    ]
    readonly_fields = ["legacy_notes", "legacy_reference"]


@admin.register(ContactGroup)
class ContactGroupAdmin(ModelAdmin):
    list_display = ["name_fr", "name_de", "slug"]
    search_fields = ["name_fr", "name_de", "slug"]
    prepopulated_fields = {"slug": ["name_fr"]}


@admin.register(MembershipType)
class MembershipTypeAdmin(ModelAdmin):
    list_display = ["name_fr", "name_de", "discount_percent", "annual_fee", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name_fr", "name_de", "code"]


@admin.register(Membership)
class MembershipAdmin(ModelAdmin):
    list_display = ["contact", "type", "starts_on", "ends_on"]
    list_filter = ["type"]
    search_fields = ["contact__last_name", "contact__first_name"]
    autocomplete_fields = ["contact"]


@admin.register(Trainer)
class TrainerAdmin(ModelAdmin):
    list_display = ["contact", "bank_name", "ahv_waiver", "is_active"]
    list_filter = ["is_active", "ahv_waiver"]
    search_fields = ["contact__last_name", "contact__first_name", "contact__email"]
    autocomplete_fields = ["contact"]
    fieldsets = [
        (None, {"fields": ["contact", "is_active"]}),
        (_("Présentation"), {"fields": ["biography_fr", "biography_de"]}),
        (
            _("Coordonnées de paiement"),
            {
                "description": _(
                    "Données sensibles au sens de la nLPD. Le numéro AVS est chiffré "
                    "au repos et ne doit jamais figurer dans un export."
                ),
                "fields": [("iban", "bic"), "bank_name", "ahv_number", "ahv_waiver"],
            },
        ),
    ]
