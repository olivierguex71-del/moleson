"""Crée les référentiels métier de l'Unipop.

Ce ne sont pas des données de démonstration : les quatre régions et les trois
types d'adhésion sont des faits établis, documentés dans l'analyse des exports
Welante, et doivent exister en production. Aucune donnée personnelle ici.

La commande est idempotente — on peut la relancer après chaque déploiement sans
créer de doublon ni écraser un ajustement fait dans l'administration.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Region
from apps.contacts.models import MembershipType

#: Régions desservies. Le code forme le suffixe des codes de cours.
REGIONS = [
    {
        "code": "FR",
        "slug": "sarine",
        "name_fr": "Sarine",
        "name_de": "Saane",
        "main_city": "Fribourg",
        "position": 1,
    },
    {
        "code": "GR",
        "slug": "gruyere",
        "name_fr": "Gruyère",
        "name_de": "Greyerz",
        "main_city": "Bulle",
        "position": 2,
    },
    {
        "code": "GL",
        "slug": "glane",
        "name_fr": "Glâne",
        "name_de": "Glane",
        "main_city": "Romont",
        "position": 3,
    },
    {
        "code": "SN",
        "slug": "singine",
        "name_fr": "Singine",
        "name_de": "Sense",
        "main_city": "Düdingen",
        "position": 4,
    },
]

#: Types d'adhésion et rabais associés (analyse des exports, section 2).
#: Les collaborateurs ne figurent pas ici : c'est un rôle porté par le contact.
MEMBERSHIP_TYPES = [
    {
        "code": "supporter",
        "name_fr": "Membre supporter",
        "name_de": "Supporter-Mitglied",
        "discount_percent": Decimal("5"),
    },
    {
        "code": "actif",
        "name_fr": "Membre actif",
        "name_de": "Aktivmitglied",
        "discount_percent": Decimal("10"),
    },
    {
        "code": "bienfaiteur",
        "name_fr": "Membre bienfaiteur",
        "name_de": "Gönnermitglied",
        "discount_percent": Decimal("15"),
    },
]


class Command(BaseCommand):
    help = "Crée ou met à jour les régions et les types d'adhésion."

    @transaction.atomic
    def handle(self, *args, **options):
        for donnees in REGIONS:
            _, cree = Region.objects.update_or_create(code=donnees["code"], defaults=donnees)
            self.stdout.write(f"  {'créée' if cree else 'à jour'} — région {donnees['code']}")

        for donnees in MEMBERSHIP_TYPES:
            _, cree = MembershipType.objects.update_or_create(
                code=donnees["code"], defaults=donnees
            )
            self.stdout.write(
                f"  {'créé' if cree else 'à jour'} — adhésion {donnees['code']} "
                f"({donnees['discount_percent']:.0f} %)"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(REGIONS)} régions et {len(MEMBERSHIP_TYPES)} types d'adhésion en place."
            )
        )
