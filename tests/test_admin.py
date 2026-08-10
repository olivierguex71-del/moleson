"""L'administration est l'outil quotidien du secrétariat : elle doit s'ouvrir.

`manage.py check` valide la configuration mais n'exécute aucune vue : un
`fieldsets` citant un champ inexistant, un `autocomplete_fields` mal câblé ou une
propriété qui lève ne se voient qu'au chargement de la page. Ce test parcourt
donc tous les écrans enregistrés.
"""

import pytest
from django.contrib import admin
from django.urls import reverse

MODELES_ENREGISTRES = [
    (modele._meta.app_label, modele._meta.model_name)
    for modele in admin.site._registry
    if modele._meta.app_label.startswith(("contacts", "catalog", "enrolments", "communications"))
]


@pytest.mark.django_db
@pytest.mark.parametrize(("app_label", "model_name"), MODELES_ENREGISTRES)
def test_la_liste_s_affiche(admin_client, app_label, model_name):
    url = reverse(f"admin:{app_label}_{model_name}_changelist")

    reponse = admin_client.get(url)

    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(("app_label", "model_name"), MODELES_ENREGISTRES)
def test_le_formulaire_de_creation_s_affiche(admin_client, app_label, model_name):
    url = reverse(f"admin:{app_label}_{model_name}_add")

    reponse = admin_client.get(url)

    assert reponse.status_code == 200


@pytest.mark.django_db
def test_tous_les_modules_metier_sont_administrables():
    """Garde-fou : une entité ajoutée sans écran resterait invisible au secrétariat."""
    attendus = {
        ("contacts", "contact"),
        ("contacts", "contactgroup"),
        ("contacts", "membership"),
        ("contacts", "membershiptype"),
        ("contacts", "trainer"),
        ("catalog", "region"),
        ("catalog", "period"),
        ("catalog", "subject"),
        ("catalog", "location"),
        ("catalog", "room"),
        ("catalog", "holiday"),
        ("catalog", "course"),
        ("catalog", "coursesession"),
        ("enrolments", "enrolment"),
        ("communications", "mailingcampaign"),
        ("communications", "mailingdelivery"),
    }

    assert attendus <= set(MODELES_ENREGISTRES)


@pytest.mark.django_db
def test_la_fiche_d_une_inscription_explique_son_prix(admin_client):
    """Le secrétariat doit pouvoir justifier un montant, pas seulement l'afficher."""
    from datetime import date
    from decimal import Decimal

    from tests.factories import EnrolmentFactory, MembershipFactory

    inscription = EnrolmentFactory()
    MembershipFactory(contact=inscription.participant, starts_on=date(2026, 1, 1))

    url = reverse("admin:enrolments_enrolment_change", args=[inscription.pk])
    reponse = admin_client.get(url)

    assert reponse.status_code == 200
    assert inscription.price == Decimal("270.00")
    assert b"270.00" in reponse.content
