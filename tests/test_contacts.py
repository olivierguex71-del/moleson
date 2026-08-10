"""Contacts : formule d'appel, rabais, doublons, adhésions, données de paie."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from apps.contacts.models import Contact, DiscountSource, MembershipType, Salutation
from tests.factories import (
    IBAN_DE_TEST,
    ContactFactory,
    MembershipFactory,
    MembershipTypeFactory,
    TrainerFactory,
)

pytestmark = pytest.mark.django_db


# --- Formule d'appel -------------------------------------------------------


@pytest.mark.parametrize(
    ("civilite", "langue", "attendu"),
    [
        (Salutation.MADAM, "fr", "Madame Exemple"),
        (Salutation.SIR, "fr", "Monsieur Exemple"),
        (Salutation.MADAM, "de", "Sehr geehrte Frau Exemple"),
        (Salutation.SIR, "de", "Sehr geehrter Herr Exemple"),
    ],
)
def test_la_formule_d_appel_suit_la_civilite_et_la_langue(civilite, langue, attendu):
    """Welante stockait la formule en texte : figée à la saisie, fausse dès qu'un nom changeait."""
    contact = ContactFactory.build(
        salutation=civilite, last_name="Exemple", correspondence_language=langue
    )

    assert contact.salutation_line() == attendu


def test_la_formule_sans_civilite_utilise_le_nom_complet():
    contact = ContactFactory.build(
        salutation=Salutation.NEUTRAL,
        first_name="Camille",
        last_name="Exemple",
        correspondence_language="fr",
    )

    assert contact.salutation_line() == "Bonjour Camille Exemple"


def test_la_formule_peut_etre_demandee_dans_une_autre_langue():
    contact = ContactFactory.build(
        salutation=Salutation.MADAM, last_name="Exemple", correspondence_language="fr"
    )

    assert contact.salutation_line("de") == "Sehr geehrte Frau Exemple"


# --- Rabais ----------------------------------------------------------------


def test_sans_adhesion_ni_role_le_rabais_est_nul():
    contact = ContactFactory()

    remise = contact.best_discount(date(2026, 9, 1))

    assert remise.percent == Decimal("0")
    assert remise.source == DiscountSource.NONE


def test_le_rabais_vient_de_l_adhesion_en_cours():
    contact = ContactFactory()
    bienfaiteur = MembershipTypeFactory(
        code="bienfaiteur", name_fr="Membre bienfaiteur", discount_percent=Decimal("15")
    )
    MembershipFactory(contact=contact, type=bienfaiteur, starts_on=date(2026, 1, 1))

    remise = contact.best_discount(date(2026, 9, 1))

    assert remise.percent == Decimal("15")
    assert remise.source == DiscountSource.MEMBERSHIP
    assert remise.label == "Membre bienfaiteur"


def test_le_statut_collaborateur_donne_dix_pour_cent():
    contact = ContactFactory(is_collaborator=True)

    remise = contact.best_discount(date(2026, 9, 1))

    assert remise.percent == Decimal("10")
    assert remise.source == DiscountSource.COLLABORATOR


def test_les_rabais_ne_se_cumulent_jamais():
    """Un bienfaiteur (15 %) également collaborateur (10 %) obtient 15 %, pas 25 %."""
    contact = ContactFactory(is_collaborator=True)
    bienfaiteur = MembershipTypeFactory(code="bienfaiteur", discount_percent=Decimal("15"))
    MembershipFactory(contact=contact, type=bienfaiteur, starts_on=date(2026, 1, 1))

    assert contact.best_discount(date(2026, 9, 1)).percent == Decimal("15")


def test_le_meilleur_rabais_l_emporte_meme_s_il_vient_du_role():
    """Un collaborateur (10 %) simple membre supporter (5 %) garde ses 10 %."""
    contact = ContactFactory(is_collaborator=True)
    supporter = MembershipTypeFactory(code="supporter", discount_percent=Decimal("5"))
    MembershipFactory(contact=contact, type=supporter, starts_on=date(2026, 1, 1))

    remise = contact.best_discount(date(2026, 9, 1))

    assert remise.percent == Decimal("10")
    assert remise.source == DiscountSource.COLLABORATOR


def test_une_adhesion_echue_ne_donne_plus_de_rabais():
    contact = ContactFactory()
    MembershipFactory(contact=contact, starts_on=date(2025, 1, 1), ends_on=date(2026, 1, 1))

    assert contact.best_discount(date(2026, 9, 1)).percent == Decimal("0")
    assert contact.best_discount(date(2025, 6, 1)).percent == Decimal("10")


# --- Adhésions -------------------------------------------------------------


def test_deux_adhesions_simultanees_sont_refusees_par_la_base():
    """La règle tient quel que soit le chemin d'écriture, script de migration compris."""
    contact = ContactFactory()
    MembershipFactory(contact=contact, starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1))

    with pytest.raises(IntegrityError):
        MembershipFactory(
            contact=contact,
            type=MembershipTypeFactory(code="supporter"),
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 12, 1),
        )


def test_des_adhesions_qui_se_suivent_sont_acceptees():
    """La borne haute est exclue : une adhésion peut commencer le jour où l'autre finit."""
    contact = ContactFactory()
    MembershipFactory(contact=contact, starts_on=date(2025, 1, 1), ends_on=date(2026, 1, 1))
    MembershipFactory(
        contact=contact,
        type=MembershipTypeFactory(code="supporter"),
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )

    assert contact.memberships.count() == 2


def test_deux_contacts_peuvent_adherer_sur_la_meme_periode():
    MembershipFactory(starts_on=date(2026, 1, 1))
    MembershipFactory(starts_on=date(2026, 1, 1))

    assert MembershipType.objects.get(code="actif").memberships.count() == 2


# --- Détection de doublons -------------------------------------------------


def test_la_recherche_par_similarite_retrouve_une_coquille():
    """« Villars -sur-Glâne » et « Villars-sur-Glane » désignent la même chose."""
    ContactFactory(last_name="Villars-sur-Glâne")
    ContactFactory(last_name="Rossier")

    proches = Contact.objects.similar_to(last_name="Villars-sur-Glane")

    assert [contact.last_name for contact in proches] == ["Villars-sur-Glâne"]


def test_la_recherche_par_similarite_tient_compte_du_courriel():
    ContactFactory(last_name="Aebischer", email="a.aebischer@example.invalid")

    proches = Contact.objects.similar_to(last_name="Inconnu", email="a.aebischer@example.invalid")

    assert proches.count() == 1


def test_un_contact_sans_rapport_n_est_pas_signale():
    ContactFactory(last_name="Rossier")

    assert Contact.objects.similar_to(last_name="Zbinden").count() == 0


# --- Contraintes et données de paie ---------------------------------------


def test_un_contact_sans_nom_ni_organisation_est_refuse():
    with pytest.raises(IntegrityError):
        Contact.objects.create(last_name="", organisation="", first_name="Sans nom")


def test_une_organisation_sans_nom_de_famille_est_valide():
    contact = ContactFactory(last_name="", first_name="", organisation="Entreprise fictive SA")

    assert contact.is_organisation
    assert str(contact) == "Entreprise fictive SA"


def test_l_iban_est_normalise_a_l_enregistrement():
    """Les exports mêlent IBAN espacés et collés : un IBAN comparable est compacté."""
    formateur = TrainerFactory(iban="CH93 0076 2011 6238 5295 7")

    formateur.refresh_from_db()
    assert formateur.iban == IBAN_DE_TEST
    assert formateur.formatted_iban == "CH93 0076 2011 6238 5295 7"


def test_un_iban_a_cle_fausse_est_refuse():
    formateur = TrainerFactory.build(iban="CH9300762011623852958")

    with pytest.raises(ValidationError) as erreur:
        formateur.clean()

    assert "iban" in erreur.value.message_dict


def test_le_numero_avs_est_illisible_en_base():
    """Contrôle nLPD : la donnée sensible ne doit pas apparaître en clair dans la table."""
    formateur = TrainerFactory(ahv_number="756.0000.0000.00")

    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT ahv_number FROM contacts_trainer WHERE id = %s", [formateur.pk])
        (stocke,) = cursor.fetchone()

    assert "756" not in stocke
    formateur.refresh_from_db()
    assert formateur.ahv_number == "756.0000.0000.00"


def test_le_npa_suisse_est_controle():
    contact = ContactFactory.build(postal_code="17000", country="CH")

    with pytest.raises(ValidationError) as erreur:
        contact.clean()

    assert "postal_code" in erreur.value.message_dict


def test_un_code_postal_etranger_echappe_au_controle_suisse():
    """Un participant frontalier a un code postal qui n'est pas un NPA."""
    contact = ContactFactory.build(postal_code="25000", country="FR")

    contact.clean()  # ne doit pas lever


def test_l_adresse_s_imprime_sans_ligne_vide():
    contact = ContactFactory.build(
        street="Route de la Gruyère",
        house_number="12",
        address_complement="",
        postal_code="1630",
        city="Bulle",
    )

    assert contact.address_lines() == ["Route de la Gruyère 12", "1630 Bulle"]
