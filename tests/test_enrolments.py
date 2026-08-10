"""Inscriptions : facturation, prix effectif et reconduction.

La reconduction est le workflow central de l'Unipop — chez Welante, une copie
manuelle par le secrétariat, marquée d'un statut « Copié » qui ne disait pas si
la personne avait accepté.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db.utils import IntegrityError

from apps.contacts.models import DiscountSource
from apps.enrolments.models import Enrolment, EnrolmentSource, EnrolmentStatus
from tests.factories import (
    ContactFactory,
    CourseFactory,
    EnrolmentFactory,
    MembershipFactory,
    MembershipTypeFactory,
    PeriodFactory,
)

pytestmark = pytest.mark.django_db


# --- Facturation -----------------------------------------------------------


def test_par_defaut_le_participant_est_facture():
    inscription = EnrolmentFactory()

    assert inscription.invoiced_contact == inscription.participant


def test_un_contact_de_facturation_distinct_est_possible():
    """Huit cas dans les exports : employeur, proche. Requis aussi par Accounto."""
    employeur = ContactFactory(last_name="", first_name="", organisation="Entreprise fictive SA")
    inscription = EnrolmentFactory(billing_contact=employeur)

    assert inscription.invoiced_contact == employeur
    assert inscription.participant != employeur


def test_le_rabais_suit_le_participant_et_non_le_payeur():
    """C'est la personne qui suit le cours dont l'adhésion ouvre droit à la réduction."""
    participant = ContactFactory()
    MembershipFactory(
        contact=participant,
        type=MembershipTypeFactory(code="bienfaiteur", discount_percent=Decimal("15")),
        starts_on=date(2026, 1, 1),
    )
    employeur = ContactFactory(last_name="", organisation="Entreprise fictive SA")

    inscription = EnrolmentFactory(participant=participant, billing_contact=employeur)

    assert inscription.price == Decimal("255.00")


# --- Prix effectif ---------------------------------------------------------


def test_le_prix_par_defaut_est_le_prix_de_base_du_cours():
    inscription = EnrolmentFactory()

    assert inscription.price == Decimal("300.00")
    assert inscription.discount_source == DiscountSource.NONE


def test_l_adhesion_du_participant_reduit_le_prix():
    participant = ContactFactory()
    MembershipFactory(contact=participant, starts_on=date(2026, 1, 1))  # actif, 10 %

    inscription = EnrolmentFactory(participant=participant)

    assert inscription.price == Decimal("270.00")
    assert inscription.discount_source == DiscountSource.MEMBERSHIP


def test_un_cours_intensif_annule_le_rabais_du_membre():
    participant = ContactFactory()
    MembershipFactory(contact=participant, starts_on=date(2026, 1, 1))
    intensif = CourseFactory(is_intensive=True)

    inscription = EnrolmentFactory(participant=participant, course=intensif)

    assert inscription.price == Decimal("300.00")
    assert inscription.discount_source == DiscountSource.NONE


def test_une_promotion_ponctuelle_se_saisit_sur_l_inscription():
    """Les notes Welante mentionnent des « réductions immédiates de 5 % »."""
    inscription = EnrolmentFactory(discount_override=Decimal("5"))

    assert inscription.price == Decimal("285.00")
    assert inscription.discount_source == DiscountSource.MANUAL


def test_le_rabais_est_evalue_a_la_date_d_inscription():
    """Une adhésion souscrite après coup ne rouvre pas le prix d'une inscription passée."""
    participant = ContactFactory()
    MembershipFactory(contact=participant, starts_on=date(2026, 10, 1))
    inscription = EnrolmentFactory(participant=participant, enrolled_on=date(2026, 9, 1))

    assert inscription.price == Decimal("300.00")
    assert inscription.price_breakdown(date(2026, 11, 1)).final_price == Decimal("270.00")


def test_le_detail_du_prix_explique_le_rabais():
    participant = ContactFactory()
    MembershipFactory(
        contact=participant,
        type=MembershipTypeFactory(
            code="supporter", name_fr="Membre supporter", discount_percent=Decimal("5")
        ),
        starts_on=date(2026, 1, 1),
    )

    detail = EnrolmentFactory(participant=participant).price_breakdown()

    assert detail.explanation == "Membre supporter"
    assert detail.discount_amount == Decimal("15.00")


# --- Contraintes -----------------------------------------------------------


def test_une_personne_ne_s_inscrit_qu_une_fois_au_meme_cours():
    inscription = EnrolmentFactory()

    with pytest.raises(IntegrityError):
        EnrolmentFactory(course=inscription.course, participant=inscription.participant)


def test_un_meme_contact_peut_suivre_plusieurs_cours():
    participant = ContactFactory()
    EnrolmentFactory(participant=participant)
    EnrolmentFactory(participant=participant)

    assert participant.enrolments.count() == 2


def test_un_rabais_hors_bornes_est_refuse_par_la_base():
    with pytest.raises(IntegrityError):
        EnrolmentFactory(discount_override=Decimal("150"))


# --- Transitions -----------------------------------------------------------


def test_confirmer_une_inscription_l_horodate():
    inscription = EnrolmentFactory(status=EnrolmentStatus.PROPOSED)

    inscription.confirm()

    inscription.refresh_from_db()
    assert inscription.status == EnrolmentStatus.CONFIRMED
    assert inscription.confirmed_at is not None


def test_annuler_une_inscription_conserve_le_motif():
    inscription = EnrolmentFactory()

    inscription.cancel("Déménagement")

    inscription.refresh_from_db()
    assert inscription.status == EnrolmentStatus.CANCELLED
    assert inscription.cancellation_reason == "Déménagement"


def test_confirmer_apres_annulation_efface_la_trace_d_annulation():
    inscription = EnrolmentFactory()
    inscription.cancel("Erreur de saisie")

    inscription.confirm()

    inscription.refresh_from_db()
    assert inscription.cancelled_at is None
    assert inscription.cancellation_reason == ""


# --- Reconduction ----------------------------------------------------------


def test_la_reconduction_cree_une_inscription_a_confirmer():
    """La place n'est acquise qu'après confirmation — Welante ne le distinguait pas."""
    automne = EnrolmentFactory()
    trimestre_suivant = PeriodFactory(
        year=2027, kind="S1", starts_on=date(2027, 1, 10), ends_on=date(2027, 6, 30)
    )
    suite = CourseFactory(period=trimestre_suivant, code="2027-S1-441111-FR")

    reconduite = automne.renew_to(suite)

    assert reconduite.status == EnrolmentStatus.PROPOSED
    assert reconduite.source == EnrolmentSource.RENEWAL
    assert reconduite.participant == automne.participant


def test_la_reconduction_garde_le_contact_de_facturation():
    employeur = ContactFactory(last_name="", organisation="Entreprise fictive SA")
    automne = EnrolmentFactory(billing_contact=employeur)
    suite = CourseFactory(code="2027-S1-441111-FR")

    assert automne.renew_to(suite).billing_contact == employeur


def test_la_reconduction_ne_reporte_pas_les_promotions():
    """Un geste commercial consenti un trimestre n'engage pas le suivant."""
    automne = EnrolmentFactory(discount_override=Decimal("50"))
    suite = CourseFactory(code="2027-S1-441111-FR")

    reconduite = automne.renew_to(suite)

    assert reconduite.discount_override is None
    assert reconduite.price == Decimal("300.00")


def test_la_chaine_de_reconduction_se_remonte():
    """Ce que Welante perdait : savoir de quelle inscription une place descend."""
    premiere = EnrolmentFactory()
    deuxieme = premiere.renew_to(CourseFactory(code="2027-S1-441111-FR"))
    troisieme = deuxieme.renew_to(CourseFactory(code="2027-T4-441111-FR"))

    assert troisieme.renewed_from == deuxieme
    assert troisieme.renewed_from.renewed_from == premiere
    assert premiere.renewed_to == deuxieme


def test_les_inscriptions_a_confirmer_se_listent():
    EnrolmentFactory(status=EnrolmentStatus.CONFIRMED)
    proposee = EnrolmentFactory(status=EnrolmentStatus.PROPOSED)

    assert list(Enrolment.objects.awaiting_confirmation()) == [proposee]


def test_les_inscriptions_actives_occupent_une_place():
    """Une proposition retient la place le temps que la personne confirme."""
    cours = CourseFactory()
    EnrolmentFactory(course=cours, status=EnrolmentStatus.CONFIRMED)
    EnrolmentFactory(course=cours, status=EnrolmentStatus.PROPOSED)
    EnrolmentFactory(course=cours, status=EnrolmentStatus.CANCELLED)

    assert cours.enrolments.active().count() == 2
