"""Administration des campagnes d'envoi."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.communications.models import MailingCampaign, MailingDelivery


class MailingDeliveryInline(TabularInline):
    model = MailingDelivery
    extra = 0
    fields = ["contact", "language", "status", "sent_at", "failure_reason"]
    readonly_fields = ["sent_at"]
    autocomplete_fields = ["contact"]


@admin.register(MailingCampaign)
class MailingCampaignAdmin(ModelAdmin):
    list_display = ["name_fr", "channel", "period", "scheduled_for", "sent_at"]
    list_filter = ["channel", "period"]
    search_fields = ["name_fr", "name_de", "slug"]
    prepopulated_fields = {"slug": ["name_fr"]}
    inlines = [MailingDeliveryInline]


@admin.register(MailingDelivery)
class MailingDeliveryAdmin(ModelAdmin):
    list_display = ["campaign", "contact", "language", "status", "sent_at"]
    list_filter = ["status", "language", "campaign"]
    search_fields = ["contact__last_name", "contact__email", "campaign__name_fr"]
    autocomplete_fields = ["campaign", "contact"]
