"""Normalisation des valeurs sorties de Welante.

Principe vérifié partout ici : en cas de doute, la fonction renvoie `None` et
laisse l'appelant consigner l'anomalie. Une date devinée ou un NPA fabriqué
traverserait la migration sans bruit et se découvrirait sur un courrier retourné.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.welante.normalizers import (
    clean_text,
    normalize_city,
    normalize_iban_value,
    normalize_phone,
    normalize_postal_code,
    parse_bool,
    parse_category_path,
    parse_date,
    parse_decimal,
    parse_int_range,
    split_multi,
)

# --- Dates -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("serie", "attendue"),
    [("45658", date(2025, 1, 1)), ("46023", date(2026, 1, 1)), ("46037", date(2026, 1, 15))],
)
def test_une_date_en_serie_excel_est_convertie(serie, attendue):
    """La colonne « Créé » sort en série dans l'export brut.

    L'origine du 30 décembre 1899 absorbe le faux 29 février 1900 d'Excel : se
    tromper d'origine décalerait toutes les dates d'un ou deux jours, erreur
    d'autant plus traître qu'elle reste plausible.
    """
    assert parse_date(serie) == attendue


def test_une_date_suisse_en_texte_est_lue():
    assert parse_date("15.01.2026") == date(2026, 1, 15)


@pytest.mark.parametrize("texte", ["2026-01-15", "15/01/2026", "15-01-2026"])
def test_les_autres_formats_courants_sont_lus(texte):
    assert parse_date(texte) == date(2026, 1, 15)


@pytest.mark.parametrize("invalide", ["", "  ", "pas une date", "31.02.2026", "999999999"])
def test_une_date_illisible_renvoie_none_plutot_qu_une_approximation(invalide):
    assert parse_date(invalide) is None


# --- Montants et nombres ---------------------------------------------------


@pytest.mark.parametrize(
    ("saisi", "attendu"),
    [
        ("300", Decimal("300")),
        ("300.50", Decimal("300.50")),
        ("300,50", Decimal("300.50")),
        ("1'250.00", Decimal("1250.00")),  # apostrophe des milliers suisse
        ("CHF 478.00", Decimal("478.00")),
    ],
)
def test_les_montants_sont_lus_dans_leurs_formes_suisses(saisi, attendu):
    assert parse_decimal(saisi) == attendu


def test_un_montant_illisible_renvoie_none():
    assert parse_decimal("sur demande") is None


def test_la_plage_de_participants_se_decoupe():
    """« TN Min-Max » vaut « 5 - 8 » en texte dans l'export."""
    assert parse_int_range("5 - 8") == (5, 8)


def test_une_plage_a_une_seule_borne_ne_devine_pas_l_autre():
    assert parse_int_range("6") == (6, None)


def test_une_plage_vide_ne_renvoie_rien():
    assert parse_int_range("") == (None, None)


# --- Adresses --------------------------------------------------------------


def test_un_npa_valide_passe():
    assert normalize_postal_code("1700") == "1700"


def test_un_npa_ampute_de_son_zero_est_refuse_et_non_reconstruit():
    """Aucun NPA suisse ne commence par zéro : on ne peut pas deviner le manquant."""
    assert normalize_postal_code("700") is None


@pytest.mark.parametrize("invalide", ["", "abcd", "17000", "0"])
def test_un_npa_hors_norme_est_refuse(invalide):
    assert normalize_postal_code(invalide) is None


@pytest.mark.parametrize(
    "coquille", ["Villars -sur-Glâne", "Villars- sur-Glâne", "Villars - sur - Glâne"]
)
def test_les_coquilles_d_espacement_des_localites_sont_corrigees(coquille):
    """Ces variantes fabriquent de faux doublons de contacts."""
    assert normalize_city(coquille) == "Villars-sur-Glâne"


def test_une_localite_correcte_reste_intacte():
    assert normalize_city("Fribourg") == "Fribourg"
    assert normalize_city("Villars-sur-Glâne") == "Villars-sur-Glâne"


# --- Téléphones ------------------------------------------------------------


@pytest.mark.parametrize("saisi", ["026 305 12 34", "0263051234", "+41263051234", "0041263051234"])
def test_les_numeros_suisses_convergent_vers_une_seule_forme(saisi):
    assert normalize_phone(saisi) == "+41 26 305 12 34"


def test_un_numero_de_forme_inattendue_reste_utilisable():
    """Contrairement à une date, un numéro mal formé garde de la valeur."""
    assert normalize_phone("026 305 12 34 (prof.)") == "+41 26 305 12 34"


def test_un_numero_vide_donne_une_chaine_vide():
    assert normalize_phone("") == ""


# --- IBAN ------------------------------------------------------------------


def test_un_iban_espace_est_normalise():
    """66 IBAN espacés, 22 collés dans l'export des intervenants."""
    iban, motif = normalize_iban_value("CH93 0076 2011 6238 5295 7")

    assert iban == "CH9300762011623852957"
    assert motif == ""


def test_un_iban_a_cle_fausse_est_ecarte_avec_son_motif():
    iban, motif = normalize_iban_value("CH9300762011623852958")

    assert iban is None
    assert motif == "iban_cle"


def test_un_iban_absent_est_signale_comme_tel():
    iban, motif = normalize_iban_value("")

    assert iban is None
    assert motif == "absent"


# --- Listes et catégories --------------------------------------------------


def test_les_categories_multiples_se_decoupent():
    valeur = "Cours de langues > Italien; Newsletter; Highlight"

    assert split_multi(valeur) == ["Cours de langues > Italien", "Newsletter", "Highlight"]


def test_une_hierarchie_de_categorie_se_separe():
    assert parse_category_path("Cours de langues > Italien") == ("Cours de langues", "Italien")


def test_une_categorie_sans_hierarchie_remonte_comme_parente():
    assert parse_category_path("Sports & Loisirs") == ("Sports & Loisirs", "")


# --- Divers ----------------------------------------------------------------


@pytest.mark.parametrize("vrai", ["1", "oui", "ja", "x", "true", "100%"])
def test_les_booleens_welante_sont_reconnus(vrai):
    assert parse_bool(vrai) is True


@pytest.mark.parametrize("faux", ["0", "non", "nein", "", "0%"])
def test_les_valeurs_fausses_le_restent(faux):
    assert parse_bool(faux) is False


def test_les_espaces_insecables_et_multiples_disparaissent():
    assert clean_text("  Anglais  niveau   A1 \n") == "Anglais niveau A1"
