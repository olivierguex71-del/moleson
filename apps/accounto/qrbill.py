"""Contrôle de conformité d'un PDF de QR-facture.

Toute la Phase 0 tient dans une question : **l'API rend-elle un PDF portant une
QR-facture conforme, ou seulement un document que l'interface d'Accounto sait
afficher ?** Si la réponse est non, c'est la Phase 2 entière qui change de forme
— d'où l'intérêt de la poser avant de construire dessus.

Ce module ne décode pas l'image du QR : cela demanderait une bibliothèque native
supplémentaire pour un gain limité. Il vérifie ce qui rend une facture
réellement payable :

- le document est bien un PDF lisible ;
- il porte les mentions normalisées du bulletin (récépissé, section paiement) ;
- l'IBAN annoncé est valide, et un QR-IBAN quand une référence QRR est utilisée ;
- la référence structurée passe son contrôle de clé ;
- le montant et la devise figurent.

Une référence dont la clé est fausse produit un paiement que la banque ne sait
pas rapprocher : l'argent arrive sans qu'on sache de qui. C'est le contrôle qui
distingue un document plausible d'un document juste.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.validators import (
    is_qr_iban,
    normalize_iban,
    normalize_reference,
    validate_iban,
    validate_qr_reference,
)

#: Mentions imposées par la norme, dans les langues nationales utilisées ici.
MENTIONS_RECEPISSE = ("récépissé", "recepisse", "empfangsschein", "receipt")
MENTIONS_SECTION_PAIEMENT = ("section paiement", "zahlteil", "payment part")

_IBAN_DANS_TEXTE = re.compile(r"\bCH\s?\d{2}(?:\s?[A-Z0-9]{1,4}){3,7}\b", re.IGNORECASE)
_REFERENCE_DANS_TEXTE = re.compile(r"\b\d{2}(?:\s\d{5}){5}\b|\b\d{27}\b")
_MONTANT_DANS_TEXTE = re.compile(r"\b\d{1,3}(?:[ ']\d{3})*[.,]\d{2}\b")


@dataclass
class Constat:
    """Un point de contrôle et son verdict."""

    libelle: str
    conforme: bool
    detail: str = ""

    def __str__(self) -> str:
        marque = "✓" if self.conforme else "✗"
        return f"{marque} {self.libelle}" + (f" — {self.detail}" if self.detail else "")


@dataclass
class RapportQrFacture:
    """Ce que vaut un PDF au regard de la norme QR-facture."""

    constats: list[Constat] = field(default_factory=list)
    iban: str = ""
    reference: str = ""

    def ajouter(self, libelle: str, conforme: bool, detail: str = "") -> None:
        self.constats.append(Constat(libelle, conforme, detail))

    @property
    def conforme(self) -> bool:
        return bool(self.constats) and all(constat.conforme for constat in self.constats)

    @property
    def echecs(self) -> list[Constat]:
        return [constat for constat in self.constats if not constat.conforme]


def extraire_texte(pdf: bytes) -> str:
    """Rend le texte d'un PDF, ou lève si le document n'en est pas un."""
    from io import BytesIO

    from pypdf import PdfReader

    lecteur = PdfReader(BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in lecteur.pages)


def verifier_pdf(pdf: bytes, *, montant_attendu: Decimal | None = None) -> RapportQrFacture:
    """Contrôle un PDF rendu par Accounto."""
    rapport = RapportQrFacture()

    if not pdf.startswith(b"%PDF"):
        rapport.ajouter(
            "le contenu est un PDF",
            False,
            "le document ne commence pas par l'en-tête PDF — l'API a peut-être "
            "rendu une page HTML ou une erreur",
        )
        return rapport
    rapport.ajouter("le contenu est un PDF", True, f"{len(pdf) // 1024} Ko")

    try:
        texte = extraire_texte(pdf)
    except Exception as exc:  # pypdf remonte des erreurs variées
        rapport.ajouter("le PDF est lisible", False, str(exc)[:120])
        return rapport
    rapport.ajouter("le PDF est lisible", True)

    minuscules = texte.lower()

    recepisse = any(mention in minuscules for mention in MENTIONS_RECEPISSE)
    rapport.ajouter(
        "le bulletin porte la mention « Récépissé »",
        recepisse,
        "" if recepisse else "mention introuvable dans le texte du PDF",
    )

    section = any(mention in minuscules for mention in MENTIONS_SECTION_PAIEMENT)
    rapport.ajouter(
        "le bulletin porte la mention « Section paiement »",
        section,
        "" if section else "mention introuvable dans le texte du PDF",
    )

    _verifier_iban(texte, rapport)
    _verifier_reference(texte, rapport)
    _verifier_montant(texte, rapport, montant_attendu)

    return rapport


def _verifier_iban(texte: str, rapport: RapportQrFacture) -> None:
    candidats = [normalize_iban(trouve) for trouve in _IBAN_DANS_TEXTE.findall(texte)]
    valides = []
    for candidat in candidats:
        try:
            validate_iban(candidat)
        except ValidationError:
            continue
        valides.append(candidat)

    if not valides:
        rapport.ajouter(
            "un IBAN valide figure sur le bulletin",
            False,
            f"{len(candidats)} suite(s) ressemblant à un IBAN, aucune à clé valide",
        )
        return

    rapport.iban = valides[0]
    rapport.ajouter("un IBAN valide figure sur le bulletin", True, rapport.iban)


def _verifier_reference(texte: str, rapport: RapportQrFacture) -> None:
    candidats = [normalize_reference(trouve) for trouve in _REFERENCE_DANS_TEXTE.findall(texte)]
    conformes = []
    for candidat in candidats:
        try:
            validate_qr_reference(candidat)
        except ValidationError:
            continue
        conformes.append(candidat)

    if not conformes:
        rapport.ajouter(
            "la référence structurée passe son contrôle de clé",
            False,
            f"{len(candidats)} suite(s) de 27 chiffres, aucune à clé valide"
            if candidats
            else "aucune référence de 27 chiffres trouvée",
        )
        return

    rapport.reference = conformes[0]
    rapport.ajouter("la référence structurée passe son contrôle de clé", True, rapport.reference)

    # Une référence QRR n'a de sens qu'avec un QR-IBAN : les apparier de travers
    # produit une facture que la banque refuse.
    if rapport.iban:
        accorde = is_qr_iban(rapport.iban)
        rapport.ajouter(
            "le QR-IBAN s'accorde avec la référence QRR",
            accorde,
            ""
            if accorde
            else "référence structurée présentée avec un IBAN ordinaire — "
            "la banque rejetterait le bulletin",
        )


def _verifier_montant(texte: str, rapport: RapportQrFacture, attendu: Decimal | None) -> None:
    devise = "chf" in texte.lower()
    rapport.ajouter("la devise CHF est mentionnée", devise)

    montants = _MONTANT_DANS_TEXTE.findall(texte)
    if not montants:
        rapport.ajouter("un montant figure sur le bulletin", False, "aucun montant reconnu")
        return
    rapport.ajouter("un montant figure sur le bulletin", True, f"{len(montants)} trouvé(s)")

    if attendu is None:
        return

    normalises = {Decimal(m.replace("'", "").replace(" ", "").replace(",", ".")) for m in montants}
    present = attendu in normalises
    rapport.ajouter(
        f"le montant facturé ({attendu} CHF) apparaît sur le bulletin",
        present,
        "" if present else "montant demandé introuvable dans le document rendu",
    )
