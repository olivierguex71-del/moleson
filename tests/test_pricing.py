"""Le calcul du prix — règle métier la plus scrutée du projet.

Tests sans base de données : la fonction est pure, elle doit le rester.
"""

from decimal import Decimal

import pytest

from apps.enrolments.pricing import compute_price

PRIX_DE_BASE = Decimal("300.00")


def test_sans_rabais_le_prix_est_le_prix_de_base():
    detail = compute_price(base_price=PRIX_DE_BASE)

    assert detail.final_price == Decimal("300.00")
    assert detail.discount_amount == Decimal("0.00")
    assert not detail.has_discount


@pytest.mark.parametrize(
    ("rabais", "attendu"),
    [
        (Decimal("5"), Decimal("285.00")),  # membre supporter
        (Decimal("10"), Decimal("270.00")),  # membre actif, collaborateur
        (Decimal("15"), Decimal("255.00")),  # membre bienfaiteur
    ],
)
def test_rabais_des_types_de_membres(rabais, attendu):
    detail = compute_price(base_price=PRIX_DE_BASE, contact_discount_percent=rabais)

    assert detail.final_price == attendu
    assert detail.discount_percent == rabais


def test_un_cours_intensif_neutralise_le_rabais_du_membre():
    detail = compute_price(
        base_price=PRIX_DE_BASE, is_intensive=True, contact_discount_percent=Decimal("15")
    )

    assert detail.final_price == PRIX_DE_BASE
    assert detail.discount_amount == Decimal("0.00")
    assert "intensif" in detail.explanation.lower()


def test_le_rabais_manuel_prime_sur_le_cours_intensif():
    """Le secrétariat doit pouvoir faire un geste commercial, y compris sur un intensif.

    Interdire toute remise sur les cours intensifs serait une règle que personne
    n'a demandée : la neutralisation vise les rabais automatiques.
    """
    detail = compute_price(
        base_price=PRIX_DE_BASE,
        is_intensive=True,
        contact_discount_percent=Decimal("15"),
        discount_override=Decimal("5"),
    )

    assert detail.final_price == Decimal("285.00")
    assert detail.discount_percent == Decimal("5")


def test_le_rabais_manuel_remplace_celui_du_membre_sans_s_y_ajouter():
    """Une promotion de 5 % accordée à un membre à 10 % donne 5 %, pas 15 %."""
    detail = compute_price(
        base_price=PRIX_DE_BASE,
        contact_discount_percent=Decimal("10"),
        discount_override=Decimal("5"),
    )

    assert detail.discount_percent == Decimal("5")
    assert detail.final_price == Decimal("285.00")


def test_le_prix_impose_remplace_tout():
    detail = compute_price(
        base_price=PRIX_DE_BASE,
        contact_discount_percent=Decimal("15"),
        price_override=Decimal("100.00"),
    )

    assert detail.final_price == Decimal("100.00")
    assert detail.discount_amount == Decimal("200.00")


def test_un_prix_impose_de_zero_est_respecte():
    """Cas réel : cours offert. Zéro n'est pas « pas de surcharge »."""
    detail = compute_price(base_price=PRIX_DE_BASE, price_override=Decimal("0"))

    assert detail.final_price == Decimal("0.00")


def test_un_rabais_de_zero_pour_cent_est_respecte():
    """Zéro explicite doit neutraliser le rabais du membre, pas être ignoré."""
    detail = compute_price(
        base_price=PRIX_DE_BASE,
        contact_discount_percent=Decimal("15"),
        discount_override=Decimal("0"),
    )

    assert detail.final_price == PRIX_DE_BASE


@pytest.mark.parametrize(
    ("rabais", "borne"),
    [(Decimal("-10"), Decimal("0")), (Decimal("150"), Decimal("100"))],
)
def test_le_rabais_reste_entre_0_et_100_pour_cent(rabais, borne):
    detail = compute_price(base_price=PRIX_DE_BASE, discount_override=rabais)

    assert detail.discount_percent == borne


def test_l_arrondi_se_fait_au_centime():
    """478 CHF à 15 % donne 71.70 exactement ; on vérifie l'absence de dérive binaire."""
    detail = compute_price(base_price=Decimal("478.00"), contact_discount_percent=Decimal("15"))

    assert detail.discount_amount == Decimal("71.70")
    assert detail.final_price == Decimal("406.30")
    assert detail.base_price - detail.discount_amount == detail.final_price


def test_l_arrondi_d_un_demi_centime_monte():
    """333.33 à 5 % vaut 16.6665 : arrondi commercial à 16.67."""
    detail = compute_price(base_price=Decimal("333.33"), contact_discount_percent=Decimal("5"))

    assert detail.discount_amount == Decimal("16.67")
    assert detail.final_price == Decimal("316.66")


def test_le_detail_porte_l_explication_du_rabais():
    detail = compute_price(
        base_price=PRIX_DE_BASE,
        contact_discount_percent=Decimal("15"),
        contact_discount_label="Membre bienfaiteur",
    )

    assert detail.explanation == "Membre bienfaiteur"
