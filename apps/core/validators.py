"""Validateurs et normalisateurs des données suisses.

Les exports Welante arrivent sales : IBAN tantôt espacés tantôt collés, NPA en
texte, localités avec des coquilles. La normalisation appartient au modèle, pas
aux seuls scripts de migration — une saisie manuelle produit les mêmes écarts.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#: Un IBAN est fait de lettres et de chiffres, sans séparateur, 15 à 34 caractères.
_IBAN_FORME = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def normalize_iban(value: str) -> str:
    """Compacte un IBAN : sans espaces, en majuscules.

    Forme de stockage : c'est elle qui rend deux IBAN comparables, alors que les
    exports Welante en contiennent 66 espacés et 22 collés.
    """
    return re.sub(r"[\s -]", "", value or "").upper()


def format_iban(value: str) -> str:
    """Rend un IBAN lisible, par groupes de quatre — forme d'affichage uniquement."""
    compact = normalize_iban(value)
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


def validate_iban(value: str) -> None:
    """Vérifie la structure et la clé de contrôle mod-97 (norme ISO 13616).

    La clé détecte les fautes de frappe et les chiffres intervertis, ce qu'un
    simple contrôle de longueur laisserait passer — sur un IBAN de paiement de
    formateur, l'erreur se paie en virement perdu.
    """
    compact = normalize_iban(value)
    if not _IBAN_FORME.match(compact):
        raise ValidationError(
            _("« %(value)s » n'a pas la forme d'un IBAN."),
            code="iban_forme",
            params={"value": value},
        )

    # Les quatre premiers caractères passent à la fin, puis chaque lettre devient
    # sa position dans l'alphabet + 9 (A=10 … Z=35) ; le reste modulo 97 doit valoir 1.
    permute = compact[4:] + compact[:4]
    try:
        entier = int("".join(str(int(caractere, 36)) for caractere in permute))
    except ValueError as exc:  # caractère hors [0-9A-Z]
        raise ValidationError(
            _("« %(value)s » contient un caractère invalide."),
            code="iban_caractere",
            params={"value": value},
        ) from exc

    if entier % 97 != 1:
        raise ValidationError(
            _("La clé de contrôle de l'IBAN « %(value)s » est fausse."),
            code="iban_cle",
            params={"value": value},
        )


#: Table du calcul de clé « modulo 10 récursif » (norme SIX pour la référence QRR).
#: Chaque chiffre lu fait passer d'un report au suivant ; le complément à dix du
#: report final donne le chiffre de contrôle.
_REPORTS_MOD10 = (
    (0, 9, 4, 6, 8, 2, 7, 1, 3, 5),
    (9, 4, 6, 8, 2, 7, 1, 3, 5, 0),
    (4, 6, 8, 2, 7, 1, 3, 5, 0, 9),
    (6, 8, 2, 7, 1, 3, 5, 0, 9, 4),
    (8, 2, 7, 1, 3, 5, 0, 9, 4, 6),
    (2, 7, 1, 3, 5, 0, 9, 4, 6, 8),
    (7, 1, 3, 5, 0, 9, 4, 6, 8, 2),
    (1, 3, 5, 0, 9, 4, 6, 8, 2, 7),
    (3, 5, 0, 9, 4, 6, 8, 2, 7, 1),
    (5, 0, 9, 4, 6, 8, 2, 7, 1, 3),
)


def normalize_reference(value: str) -> str:
    """Compacte une référence de paiement : sans espaces."""
    return re.sub(r"\s", "", value or "")


def mod10_recursive(chiffres: str) -> int:
    """Chiffre de contrôle « modulo 10 récursif » d'une suite de chiffres."""
    report = 0
    for chiffre in chiffres:
        report = _REPORTS_MOD10[report][int(chiffre)]
    return (10 - report) % 10


def validate_qr_reference(value: str) -> None:
    """Vérifie une référence structurée QRR : 27 chiffres, dernier de contrôle.

    C'est le contrôle qui distingue une référence réellement conforme d'une
    suite de chiffres plausible. Une référence fausse produit un paiement que
    la banque ne sait pas rapprocher — l'argent arrive sans qu'on sache de qui.
    """
    compact = normalize_reference(value)
    if not re.fullmatch(r"\d{27}", compact):
        raise ValidationError(
            _("Une référence QRR compte 27 chiffres ; « %(value)s » n'y correspond pas."),
            code="qrr_forme",
            params={"value": value},
        )
    if mod10_recursive(compact[:26]) != int(compact[26]):
        raise ValidationError(
            _("Le chiffre de contrôle de la référence « %(value)s » est faux."),
            code="qrr_cle",
            params={"value": value},
        )


def is_qr_iban(value: str) -> bool:
    """Dit si un IBAN suisse est un QR-IBAN.

    Un QR-IBAN se reconnaît à son identifiant d'institution compris entre 30000
    et 31999 : c'est lui qui impose une référence structurée QRR. Confondre les
    deux fait produire des factures que la banque refuse.
    """
    compact = normalize_iban(value)
    if not re.fullmatch(r"CH\d{2}\d{5}.*", compact):
        return False
    return 30000 <= int(compact[4:9]) <= 31999


def validate_swiss_postal_code(value: str) -> None:
    """Un NPA suisse est un nombre de quatre chiffres entre 1000 et 9999."""
    if not re.fullmatch(r"\d{4}", value or "") or not 1000 <= int(value) <= 9999:
        raise ValidationError(
            _("« %(value)s » n'est pas un NPA suisse."),
            code="npa",
            params={"value": value},
        )
