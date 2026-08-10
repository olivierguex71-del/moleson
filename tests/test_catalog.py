"""Catalogue : codes de cours, périodes, taxonomie, occupation des salles."""

from datetime import date, datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone

from apps.catalog.course_codes import build_course_code, is_canonical, parse_course_code
from apps.catalog.models import PeriodKind, SessionStatus
from tests.factories import (
    CourseFactory,
    CourseSessionFactory,
    PeriodFactory,
    RegionFactory,
    RoomFactory,
    SubjectFactory,
)

# --- Codes de cours (sans base de données) ---------------------------------


def test_un_code_canonique_se_decompose():
    parts = parse_course_code("2026-T4-441111-FR")

    assert (parts.year, parts.period, parts.number) == (2026, "T4", "441111")
    assert parts.region == "FR"
    assert parts.variant == ""


def test_la_variante_est_reconnue():
    """Le code de la facture 184008 porte une variante : « 421111b »."""
    parts = parse_course_code("2026-S1-421111b-GR")

    assert parts.number == "421111"
    assert parts.variant == "b"


def test_le_prefixe_designe_la_famille_de_matieres():
    """44xxxx anglais, 42xxxx italien, 72xxxx aquatique."""
    assert parse_course_code("2026-T4-441111-FR").subject_prefix == "44"
    assert parse_course_code("2026-T4-721111-SN").subject_prefix == "72"


@pytest.mark.parametrize("region", ["FR", "GR", "GL", "SN"])
def test_le_suffixe_est_la_region_et_non_la_langue(region):
    """Confusion facile — et qui coûterait une migration entière à corriger."""
    assert parse_course_code(f"2026-T4-441111-{region}").region == region


@pytest.mark.parametrize(
    "ancien",
    ["1617-272-318", "2021-72-1021-SN", "", "n'importe quoi"],
)
def test_un_code_herite_n_est_pas_une_erreur_mais_reste_indecomposable(ancien):
    """Les codes d'avant 2023 suivent d'autres formes : on renvoie None, on ne lève pas."""
    assert parse_course_code(ancien) is None
    assert not is_canonical(ancien)


def test_un_code_se_reconstruit_a_partir_de_ses_composants():
    code = build_course_code(year=2026, period="T4", number="441111", region="FR", variant="b")

    assert code == "2026-T4-441111b-FR"
    assert is_canonical(code)


# --- Cohérence du code avec la période et la région ------------------------


@pytest.mark.django_db
def test_un_code_incoherent_avec_la_region_est_refuse():
    gruyere = RegionFactory(code="GR", slug="gruyere", name_fr="Gruyère")
    cours = CourseFactory.build(code="2026-T4-441111-FR", region=gruyere, period=PeriodFactory())

    with pytest.raises(ValidationError) as erreur:
        cours.clean()

    assert "région" in str(erreur.value)


@pytest.mark.django_db
def test_un_code_incoherent_avec_la_periode_est_refuse():
    cours = CourseFactory.build(
        code="2026-S1-441111-FR", region=RegionFactory(), period=PeriodFactory()
    )

    with pytest.raises(ValidationError) as erreur:
        cours.clean()

    assert "période" in str(erreur.value)


@pytest.mark.django_db
def test_un_code_herite_echappe_au_controle_de_coherence():
    """Sinon aucune donnée d'avant 2023 ne pourrait être importée."""
    cours = CourseFactory.build(
        code="2021-72-1021-SN", region=RegionFactory(), period=PeriodFactory()
    )

    cours.clean()  # ne doit pas lever
    assert cours.canonical_code is None


@pytest.mark.django_db
def test_le_code_canonique_se_recalcule_depuis_les_relations():
    cours = CourseFactory(code="2026-T4-441111-FR")

    assert cours.canonical_code == "2026-T4-441111-FR"


# --- Périodes --------------------------------------------------------------


@pytest.mark.django_db
def test_la_periode_suivante_est_chronologique_et_non_alphabetique():
    """Trié sur le code, S1 précéderait T4 et la reconduction viserait le passé."""
    automne = PeriodFactory(
        year=2026, kind=PeriodKind.T4, starts_on=date(2026, 9, 1), ends_on=date(2026, 12, 20)
    )
    printemps = PeriodFactory(
        year=2027, kind=PeriodKind.S1, starts_on=date(2027, 1, 10), ends_on=date(2027, 6, 30)
    )

    assert automne.next_period() == printemps
    assert printemps.next_period() is None


@pytest.mark.django_db
def test_une_periode_ne_peut_pas_finir_avant_de_commencer():
    with pytest.raises(IntegrityError):
        PeriodFactory(
            year=2030, kind=PeriodKind.T1, starts_on=date(2030, 6, 1), ends_on=date(2030, 1, 1)
        )


@pytest.mark.django_db
def test_le_code_de_periode_est_celui_du_code_de_cours():
    periode = PeriodFactory(year=2026, kind=PeriodKind.T4)

    assert periode.code == "2026-T4"


# --- Taxonomie -------------------------------------------------------------


@pytest.mark.django_db
def test_la_taxonomie_est_limitee_a_deux_niveaux():
    """« Cours de langues > Italien » : pas de troisième étage."""
    langues = SubjectFactory(name_fr="Cours de langues")
    italien = SubjectFactory(name_fr="Italien", parent=langues)

    troisieme = SubjectFactory.build(name_fr="Italien A1", parent=italien)
    with pytest.raises(ValidationError) as erreur:
        troisieme.clean()

    assert "deux niveaux" in str(erreur.value)


@pytest.mark.django_db
def test_une_sous_matiere_s_affiche_avec_sa_parente():
    langues = SubjectFactory(name_fr="Cours de langues")
    italien = SubjectFactory(name_fr="Italien", parent=langues)

    assert str(italien) == "Cours de langues > Italien"


@pytest.mark.django_db
def test_le_slug_reprend_le_web_code_welante():
    """Conserver l'identifiant public évite de casser les URL du site et leur référencement."""
    matiere = SubjectFactory(slug="cours-de-langues", name_fr="Cours de langues")

    assert matiere.slug == "cours-de-langues"


# --- Séances et occupation des salles --------------------------------------


def _creneau(jour: date, heure: int) -> datetime:
    return timezone.make_aware(datetime.combine(jour, time(heure, 0)))


@pytest.mark.django_db
def test_deux_seances_ne_peuvent_occuper_la_meme_salle_au_meme_moment():
    salle = RoomFactory()
    debut = _creneau(date(2026, 9, 15), 18)
    CourseSessionFactory(room=salle, starts_at=debut, ends_at=debut + timedelta(hours=2))

    with pytest.raises(IntegrityError):
        CourseSessionFactory(
            room=salle, starts_at=debut + timedelta(hours=1), ends_at=debut + timedelta(hours=3)
        )


@pytest.mark.django_db
def test_deux_seances_qui_s_enchainent_dans_la_meme_salle_sont_acceptees():
    """La borne haute est exclue : un cours peut finir à 18h et le suivant commencer à 18h."""
    salle = RoomFactory()
    debut = _creneau(date(2026, 9, 15), 16)
    CourseSessionFactory(room=salle, starts_at=debut, ends_at=debut + timedelta(hours=2))
    CourseSessionFactory(
        room=salle, starts_at=debut + timedelta(hours=2), ends_at=debut + timedelta(hours=4)
    )

    assert salle.sessions.count() == 2


@pytest.mark.django_db
def test_une_seance_annulee_libere_la_salle():
    salle = RoomFactory()
    debut = _creneau(date(2026, 9, 15), 18)
    CourseSessionFactory(
        room=salle,
        starts_at=debut,
        ends_at=debut + timedelta(hours=2),
        status=SessionStatus.CANCELLED,
    )

    CourseSessionFactory(room=salle, starts_at=debut, ends_at=debut + timedelta(hours=2))

    assert salle.sessions.filter(status=SessionStatus.SCHEDULED).count() == 1


@pytest.mark.django_db
def test_des_seances_sans_salle_ne_se_bloquent_pas():
    """Un cours chez un particulier n'a pas de salle du référentiel."""
    debut = _creneau(date(2026, 9, 15), 18)
    CourseSessionFactory(room=None, starts_at=debut, ends_at=debut + timedelta(hours=2))
    CourseSessionFactory(room=None, starts_at=debut, ends_at=debut + timedelta(hours=2))


@pytest.mark.django_db
def test_une_seance_ne_peut_pas_finir_avant_de_commencer():
    debut = _creneau(date(2026, 9, 15), 18)

    with pytest.raises(IntegrityError):
        CourseSessionFactory(starts_at=debut, ends_at=debut - timedelta(hours=1))


@pytest.mark.django_db
def test_les_seances_portent_chacune_leur_horaire():
    """Une facture réelle montre « 2× mardi 15h45, 4× jeudi 16h00, 1× mardi 16h00 »."""
    cours = CourseFactory()
    CourseSessionFactory(
        course=cours,
        starts_at=_creneau(date(2026, 9, 15), 15),
        ends_at=_creneau(date(2026, 9, 15), 17),
    )
    CourseSessionFactory(
        course=cours,
        starts_at=_creneau(date(2026, 9, 17), 16),
        ends_at=_creneau(date(2026, 9, 17), 18),
    )

    horaires = [session.starts_at.astimezone().hour for session in cours.sessions.all()]
    assert horaires == [15, 16]
