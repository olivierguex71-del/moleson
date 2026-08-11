"""Validateurs des données suisses.

Les exports Welante contiennent 66 IBAN espacés, 22 collés, 19 absents, et des
localités mal saisies. La normalisation appartient au modèle : une saisie
manuelle produit exactement les mêmes écarts qu'un import.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.core.validators import (
    format_iban,
    is_qr_iban,
    normalize_iban,
    normalize_reference,
    validate_iban,
    validate_qr_reference,
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


# --- Conformité QR-facture -------------------------------------------------

# Coordonnées de paiement de l'institution, relevées dans l'analyse des exports
# (docs/analyse-exports-welante.md). Elles figurent sur toute facture émise et
# ne constituent pas une donnée personnelle.
QR_IBAN_UNIPOP = "CH21 3000 0001 1700 4851 9"
REFERENCE_UNIPOP = "00 00000 00016 65740 00018 40088"


def test_la_reference_d_une_vraie_qr_facture_est_reconnue_conforme():
    """Éprouve le calcul de clé sur un cas réel plutôt que sur un exemple inventé."""
    validate_qr_reference(REFERENCE_UNIPOP)


def test_un_seul_chiffre_modifie_est_detecte():
    """C'est tout l'objet de la clé : un paiement mal référencé arrive sans qu'on
    sache de qui il vient.
    """
    altere = REFERENCE_UNIPOP[:-1] + ("7" if REFERENCE_UNIPOP[-1] != "7" else "6")

    with pytest.raises(ValidationError) as erreur:
        validate_qr_reference(altere)

    assert erreur.value.code == "qrr_cle"


def test_deux_chiffres_intervertis_dans_la_reference_sont_detectes():
    compact = normalize_reference(REFERENCE_UNIPOP)
    interverti = compact[:20] + compact[21] + compact[20] + compact[22:]

    if interverti != compact:  # l'interversion n'a de sens que si les chiffres diffèrent
        with pytest.raises(ValidationError):
            validate_qr_reference(interverti)


@pytest.mark.parametrize("invalide", ["", "123", "00 00000 00016 65740 00018 4008", "abc"])
def test_une_reference_mal_formee_est_refusee(invalide):
    with pytest.raises(ValidationError) as erreur:
        validate_qr_reference(invalide)

    assert erreur.value.code == "qrr_forme"


def test_la_reference_se_valide_espacee_ou_compacte():
    validate_qr_reference(REFERENCE_UNIPOP)
    validate_qr_reference(normalize_reference(REFERENCE_UNIPOP))


def test_le_qr_iban_de_l_institution_est_reconnu():
    """Un QR-IBAN impose une référence structurée ; l'IBAN ordinaire, non.

    Les confondre fait produire des factures que la banque refuse.
    """
    assert is_qr_iban(QR_IBAN_UNIPOP)


def test_un_iban_ordinaire_n_est_pas_un_qr_iban():
    assert not is_qr_iban(IBAN_VALIDE)


@pytest.mark.parametrize("iban", ["CH2130000001170048519", "CH4431999123000889012"])
def test_les_identifiants_d_institution_30000_a_31999_marquent_le_qr_iban(iban):
    assert is_qr_iban(iban)


def test_un_iban_etranger_n_est_pas_un_qr_iban():
    assert not is_qr_iban("DE89370400440532013000")
