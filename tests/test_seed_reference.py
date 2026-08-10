"""Les référentiels métier sont des faits établis, pas des données de démonstration."""

from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.catalog.models import Region
from apps.contacts.models import MembershipType

pytestmark = pytest.mark.django_db


def test_les_quatre_regions_sont_creees():
    call_command("seed_reference", verbosity=0)

    assert set(Region.objects.values_list("code", flat=True)) == {"FR", "GR", "GL", "SN"}


def test_chaque_region_est_bilingue():
    """Singine en français, Sense en allemand — jamais les deux dans un même champ."""
    call_command("seed_reference", verbosity=0)

    singine = Region.objects.get(code="SN")
    assert singine.tr("name", "fr") == "Singine"
    assert singine.tr("name", "de") == "Sense"
    assert singine.main_city == "Düdingen"


def test_les_rabais_correspondent_a_l_analyse_des_exports():
    call_command("seed_reference", verbosity=0)

    rabais = dict(MembershipType.objects.values_list("code", "discount_percent"))
    assert rabais == {
        "supporter": Decimal("5.00"),
        "actif": Decimal("10.00"),
        "bienfaiteur": Decimal("15.00"),
    }


def test_les_collaborateurs_ne_sont_pas_un_type_d_adhesion():
    """C'est un rôle porté par le contact : le confondre fausserait le cumul des rabais."""
    call_command("seed_reference", verbosity=0)

    assert not MembershipType.objects.filter(code__icontains="collab").exists()


def test_la_commande_est_rejouable_sans_creer_de_doublon():
    call_command("seed_reference", verbosity=0)
    call_command("seed_reference", verbosity=0)

    assert Region.objects.count() == 4
    assert MembershipType.objects.count() == 3
