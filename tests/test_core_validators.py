"""Validateurs des données suisses.

Les exports Welante contiennent 66 IBAN espacés, 22 collés, 19 absents, et des
localités mal saisies. La normalisation appartient au modèle : une saisie
manuelle produit exactement les mêmes écarts qu'un import.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.core.validators import (
    format_iban,
    normalize_iban,
    validate_iban,
    validate_swiss_postal_code,
)

# IBAN de test à clé valide, sur des numéros de compte fictifs.
IBAN_VALIDE = "CH9300762011623852957"
QR_IBAN_VALIDE = "CH4431999123000889012"


@pytest.mark.parametrize(
    "saisi",
    ["CH93 0076 2011 6238 5295 7", "ch9300762011623852957", "CH93-0076-2011-6238-5295-7"],
)
def test_la_normalisation_ramene_toutes_les_saisies_a_la_meme_forme(saisi):
    assert normalize_iban(saisi) == IBAN_VALIDE


def test_l_affichage_regroupe_par_quatre():
    assert format_iban(IBAN_VALIDE) == "CH93 0076 2011 6238 5295 7"


@pytest.mark.parametrize("iban", [IBAN_VALIDE, QR_IBAN_VALIDE])
def test_un_iban_valide_passe(iban):
    validate_iban(iban)


def test_un_iban_espace_passe_sans_normalisation_prealable():
    validate_iban("CH93 0076 2011 6238 5295 7")


def test_deux_chiffres_intervertis_sont_detectes():
    """C'est tout l'intérêt de la clé mod-97 : un contrôle de longueur laisserait passer."""
    interverti = "CH9300762011623852975"

    with pytest.raises(ValidationError) as erreur:
        validate_iban(interverti)

    assert erreur.value.code == "iban_cle"


@pytest.mark.parametrize(
    ("invalide", "code"),
    [
        ("CH93", "iban_forme"),
        ("1234567890123456789", "iban_forme"),
        ("", "iban_forme"),
        ("CH93007620116238529$7", "iban_forme"),
    ],
)
def test_les_saisies_qui_ne_sont_pas_des_iban_sont_rejetees(invalide, code):
    with pytest.raises(ValidationError) as erreur:
        validate_iban(invalide)

    assert erreur.value.code == code


@pytest.mark.parametrize("npa", ["1700", "1630", "3186", "9999", "1000"])
def test_les_npa_suisses_passent(npa):
    """Fribourg, Bulle, Düdingen, et les bornes du plan de numérotation."""
    validate_swiss_postal_code(npa)


@pytest.mark.parametrize("npa", ["170", "17000", "0999", "abcd", ""])
def test_les_npa_hors_norme_sont_rejetes(npa):
    with pytest.raises(ValidationError):
        validate_swiss_postal_code(npa)
