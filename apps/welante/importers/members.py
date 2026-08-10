"""Import des membres.

Deux corrections d'anti-patterns Welante se jouent ici :

- les colonnes **« Programmversand Herbst 2019 », « Frühling 2020 »…** — une par
  saison — deviennent des campagnes et des envois, si bien qu'ajouter une saison
  ne modifiera plus le schéma ;
- le champ **Notes**, journal de dix ans en texte concaténé, part en archive de
  lecture seule ; les notes futures seront horodatées et attribuées.

Le mapping des anciennes catégories reste partiellement ouvert : « Mitarbeiter »
correspond au rôle collaborateur de Moléson, mais « Vorstandsmitglied » (comité)
n'a pas d'équivalent établi. Plutôt que de deviner, ces lignes sont importées
sans adhésion et signalées.
"""

from datetime import date

from apps.communications.models import (
    CampaignChannel,
    DeliveryStatus,
    MailingCampaign,
    MailingDelivery,
)
from apps.contacts.models import Membership, MembershipType
from apps.welante.columns import ColumnMapping, RowValues, normalize_header
from apps.welante.importers.base import ContactResolver
from apps.welante.normalizers import clean_text, parse_date
from apps.welante.reports import ImportReport, Severity
from apps.welante.sources import PREFIXES_CAMPAGNE
from apps.welante.workbook import Workbook

#: Correspondances certaines entre catégories Welante et types d'adhésion Moléson.
TYPES_CONNUS = {
    "supporter-mitglied": "supporter",
    "supporter": "supporter",
    "membre supporter": "supporter",
    "aktivmitglied": "actif",
    "membre actif": "actif",
    "gönnermitglied": "bienfaiteur",
    "membre bienfaiteur": "bienfaiteur",
}

#: Catégories qui désignent un rôle et non une adhésion.
ROLES = {"mitarbeiter", "collaborateur", "collaboratrice", "mitarbeiterin"}

#: Catégories dont la correspondance n'est pas tranchée (cf. analyse, section 2).
A_ARBITRER = {"vorstandsmitglied", "comité", "vorstand"}


def import_members(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
    rapport = ImportReport(source=classeur.path.name)
    resolveur = ContactResolver(report=rapport)

    if not mapping.get("last_name"):
        rapport.add(
            row=1,
            column="last_name",
            code="colonne_manquante",
            message="Colonne du nom introuvable : import impossible.",
            severity=Severity.ERROR,
        )
        return rapport

    campagnes = _colonnes_de_campagne(classeur.headers)
    if campagnes:
        rapport.add(
            row=1,
            column="—",
            code="colonnes_par_saison",
            message=(
                f"{len(campagnes)} colonnes « une par saison » converties en campagnes : "
                "le schéma ne grossira plus à chaque envoi."
            ),
        )

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1

        champs = RowValues(mapping, ligne)

        contact = resolveur.resolve(
            row=numero,
            donnees={
                "last_name": champs.get("last_name"),
                "first_name": champs.get("first_name"),
                "email": champs.get("email"),
                "street": champs.get("street"),
                "postal_code": champs.get("postal_code"),
                "city": champs.get("city"),
                "language": champs.get("language"),
                "notes": champs.get("notes"),
            },
        )
        if contact is None:
            rapport.rows_skipped += 1
            continue

        _rattacher_adhesion(
            contact=contact,
            categorie=champs.get("membership_type") or champs.get("function"),
            depuis=parse_date(ligne[mapping.get("since")]) if mapping.get("since") else None,
            rapport=rapport,
            numero=numero,
        )

        for intitule in campagnes:
            if clean_text(ligne[intitule]):
                _enregistrer_envoi(contact, intitule)

        rapport.rows_imported += 1

    return rapport


def _colonnes_de_campagne(headers: list[str]) -> list[str]:
    return [
        intitule for intitule in headers if normalize_header(intitule).startswith(PREFIXES_CAMPAGNE)
    ]


def _rattacher_adhesion(*, contact, categorie: str, depuis, rapport, numero) -> None:
    forme = clean_text(categorie).lower()
    if not forme:
        return

    if forme in ROLES:
        # Chez Moléson, collaborateur est un rôle du contact, pas un type
        # d'adhésion : c'est ce qui empêche son rabais de se cumuler.
        contact.is_collaborator = True
        contact.save(update_fields=["is_collaborator"])
        rapport.add(
            row=numero,
            column="membership_type",
            code="role_collaborateur",
            message="Catégorie reconnue comme rôle collaborateur, non comme adhésion.",
        )
        return

    if forme in A_ARBITRER:
        rapport.add(
            row=numero,
            column="membership_type",
            code="categorie_a_arbitrer",
            message=(
                "Catégorie « comité » sans équivalent établi : contact importé sans "
                "adhésion, correspondance à trancher."
            ),
            severity=Severity.REVIEW,
        )
        return

    code = TYPES_CONNUS.get(forme)
    if code is None:
        rapport.add(
            row=numero,
            column="membership_type",
            code="categorie_inconnue",
            message="Catégorie d'adhésion non reconnue : contact importé sans adhésion.",
            severity=Severity.REVIEW,
        )
        return

    type_adhesion = MembershipType.objects.filter(code=code).first()
    if type_adhesion is None:
        rapport.add(
            row=numero,
            column="membership_type",
            code="type_absent",
            message=f"Type d'adhésion « {code} » absent : lancer `seed_reference`.",
            severity=Severity.ERROR,
        )
        return

    if contact.memberships.exists():
        return

    Membership.objects.create(
        contact=contact, type=type_adhesion, starts_on=depuis or date(2020, 1, 1)
    )
    if depuis is None:
        rapport.add(
            row=numero,
            column="since",
            code="date_adhesion_inconnue",
            message="Date d'adhésion absente : début fixé au 01.01.2020, à corriger.",
            severity=Severity.REVIEW,
        )


def _enregistrer_envoi(contact, intitule: str) -> None:
    """Transforme une case cochée en envoi rattaché à une campagne."""
    campagne, _ = MailingCampaign.objects.get_or_create(
        slug=normalize_header(intitule)[:80],
        defaults={"name_fr": intitule, "name_de": intitule, "channel": CampaignChannel.POSTAL},
    )
    MailingDelivery.objects.get_or_create(
        campaign=campagne,
        contact=contact,
        defaults={
            "language": contact.correspondence_language,
            "status": DeliveryStatus.SENT,
        },
    )
