"""Outils communs aux importeurs.

Deux mécanismes y sont centralisés parce qu'ils décident de la qualité de toute
la migration :

- **la résolution des contacts**, qui détermine si deux lignes désignent la même
  personne. Un export de 349 inscriptions contient 28 contacts répétés : les
  fusionner à tort perdrait des inscriptions, ne pas les fusionner créerait les
  doublons que Moléson est censé supprimer ;
- **la création des périodes** déduites des codes de cours, avec des dates
  conventionnelles explicitement signalées comme à vérifier.
"""

from dataclasses import dataclass, field
from datetime import date

from apps.catalog.models import Period, PeriodKind, Region
from apps.contacts.models import Contact
from apps.welante.normalizers import (
    clean_text,
    normalize_city,
    normalize_phone,
    normalize_postal_code,
    parse_date,
    parse_language,
    parse_salutation,
)
from apps.welante.reports import ImportReport, Severity

#: Dates conventionnelles d'une période, à défaut d'information dans l'export.
#: Volontairement grossières : elles doivent être corrigées, et le rapport le dit.
BORNES_CONVENTIONNELLES = {
    PeriodKind.T1: ((1, 10), (3, 31)),
    PeriodKind.T2: ((4, 1), (6, 30)),
    PeriodKind.T3: ((7, 1), (8, 31)),
    PeriodKind.T4: ((9, 1), (12, 20)),
    PeriodKind.S1: ((1, 10), (6, 30)),
    PeriodKind.S2: ((7, 1), (12, 20)),
}


def contact_key(*, email: str, last_name: str, first_name: str, postal_code: str) -> str:
    """Clé d'identité d'un contact.

    Le courriel prime : c'est l'identifiant le plus fiable. À défaut — douze
    personnes n'en ont pas — on retombe sur nom, prénom et NPA, ce qui suffit à
    distinguer deux homonymes de communes différentes sans fusionner une même
    personne saisie deux fois.
    """
    if courriel := clean_text(email).lower():
        return f"email:{courriel}"
    return (
        f"nom:{clean_text(last_name).lower()}|"
        f"{clean_text(first_name).lower()}|{clean_text(postal_code)}"
    )


@dataclass
class ContactResolver:
    """Crée les contacts en les dédoublonnant au fil de l'import."""

    report: ImportReport
    cache: dict[str, Contact] = field(default_factory=dict)
    created: int = 0
    reused: int = 0

    def resolve(self, *, row: int, donnees: dict) -> Contact | None:
        """Renvoie le contact correspondant aux données d'une ligne, en le créant au besoin."""
        nom = clean_text(donnees.get("last_name"))
        prenom = clean_text(donnees.get("first_name"))
        organisation = clean_text(donnees.get("organisation"))
        if not nom and not organisation:
            self.report.add(
                row=row,
                column="last_name",
                code="contact_sans_nom",
                message="Ni nom de famille ni organisation : ligne non importable.",
                severity=Severity.ERROR,
            )
            return None

        npa = normalize_postal_code(donnees.get("postal_code"))
        if donnees.get("postal_code") and npa is None:
            self.report.add(
                row=row,
                column="postal_code",
                code="npa_invalide",
                message="NPA illisible ou hors norme suisse : adresse importée sans NPA.",
            )

        courriel = clean_text(donnees.get("email")).lower()
        if not courriel:
            self.report.add(
                row=row,
                column="email",
                code="sans_courriel",
                message="Aucun courriel : ni magic link ni envoi automatique possible.",
                severity=Severity.REVIEW,
            )

        cle = contact_key(email=courriel, last_name=nom, first_name=prenom, postal_code=npa or "")
        if contact := self.cache.get(cle):
            self.reused += 1
            return contact

        contact, cree = Contact.objects.get_or_create(
            **self._criteres(courriel, nom, prenom, organisation),
            defaults={
                "first_name": prenom,
                "last_name": nom,
                "organisation": organisation,
                "email": courriel,
                "salutation": parse_salutation(donnees.get("salutation")),
                "correspondence_language": parse_language(donnees.get("language")),
                "phone": normalize_phone(donnees.get("phone")),
                "mobile": normalize_phone(donnees.get("mobile")),
                "birth_date": parse_date(donnees.get("birth_date")),
                "street": clean_text(donnees.get("street")),
                "address_complement": clean_text(donnees.get("address_complement")),
                "postal_code": npa or "",
                "city": normalize_city(donnees.get("city")),
                "country": clean_text(donnees.get("country")).upper()[:2] or "CH",
                "legacy_notes": clean_text(donnees.get("notes")),
            },
        )
        self.cache[cle] = contact
        if cree:
            self.created += 1
        else:
            self.reused += 1
        return contact

    @staticmethod
    def _criteres(courriel: str, nom: str, prenom: str, organisation: str) -> dict:
        """Critères de recherche en base, alignés sur la clé d'identité."""
        if courriel:
            return {"email": courriel}
        return {"last_name": nom, "first_name": prenom, "organisation": organisation}


def ensure_period(*, year: int, kind: str, report: ImportReport, row: int) -> Period:
    """Renvoie la période correspondante, en la créant avec des dates à vérifier."""
    periode = Period.objects.filter(year=year, kind=kind).first()
    if periode:
        return periode

    (mois_debut, jour_debut), (mois_fin, jour_fin) = BORNES_CONVENTIONNELLES[kind]
    periode = Period.objects.create(
        year=year,
        kind=kind,
        starts_on=date(year, mois_debut, jour_debut),
        ends_on=date(year, mois_fin, jour_fin),
    )
    report.add(
        row=row,
        column="code",
        code="periode_creee",
        message=(
            f"Période {year}-{kind} créée avec des dates conventionnelles : "
            "à corriger dans l'administration."
        ),
        severity=Severity.REVIEW,
    )
    return periode


def resolve_region(code: str, *, report: ImportReport, row: int) -> Region | None:
    """Retrouve une région par son code, sans jamais l'inventer."""
    region = Region.objects.filter(code=code.upper()).first()
    if region is None:
        report.add(
            row=row,
            column="code",
            code="region_inconnue",
            message=(
                f"Suffixe régional « {code} » inconnu — lancer `seed_reference` "
                "ou corriger le code du cours."
            ),
            severity=Severity.ERROR,
        )
    return region
