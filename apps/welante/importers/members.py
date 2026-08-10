"""Import des membres.

Deux corrections d'anti-patterns Welante se jouent ici :

- les colonnes **« Programmversand Herbst 2019 », « Frühling 2020 »…** — une par
  saison — deviennent des campagnes et des envois, si bien qu'ajouter une saison
  ne modifiera plus le schéma ;
- le champ **Notes**, journal de dix ans en texte concaténé, part en archive de
  lecture seule ; les notes futures seront horodatées et attribuées.

Troisième particularité, révélée par l'inspection du fichier réel : le type
d'adhésion n'est pas une colonne à valeurs mais **trois colonnes cochées** —
« Membre supporter », « Vorstand », « Mitarbeiter ». Chacune répond à un concept
différent de Moléson : la première est une adhésion, la troisième un rôle du
contact, et la deuxième n'a pas d'équivalent établi. Les lire comme une colonne
unique aurait importé 122 membres sans aucune adhésion.

Le mapping du comité reste ouvert : plutôt que de deviner entre « membre actif »
et « membre bienfaiteur », ces lignes sont importées sans adhésion et signalées.
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
from apps.welante.normalizers import clean_text, parse_bool, parse_date
from apps.welante.reports import ImportReport, Severity, ligne_isolee
from apps.welante.sources import PREFIXES_CAMPAGNE
from apps.welante.workbook import Workbook

#: Date de début retenue quand l'export ne dit pas depuis quand la personne
#: adhère. Volontairement ancienne et signalée, pour être corrigée.
DEBUT_INCONNU = date(2020, 1, 1)


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
        with ligne_isolee(rapport, numero):
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
                    "salutation": champs.get("salutation"),
                    "organisation": champs.get("organisation"),
                    "birth_date": champs.get("birth_date"),
                    "address_complement": champs.get("address_complement"),
                    "country": champs.get("country"),
                    "notes": champs.get("notes"),
                },
            )
            if contact is None:
                rapport.rows_skipped += 1
                continue

            _rattacher_adhesion(
                contact=contact,
                champs=champs,
                depuis=parse_date(champs.get("since")),
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


def _rattacher_adhesion(*, contact, champs, depuis, rapport, numero) -> None:
    """Traduit les colonnes cochées en adhésion et en rôle.

    Les trois colonnes ne sont pas exclusives : quelqu'un peut être à la fois
    membre supporter et collaborateur. Chacune est donc traitée pour elle-même.
    """
    if parse_bool(champs.get("is_staff")):
        # Chez Moléson, collaborateur est un rôle du contact, pas un type
        # d'adhésion : c'est ce qui empêche son rabais de se cumuler avec celui
        # d'une adhésion.
        contact.is_collaborator = True
        contact.save(update_fields=["is_collaborator"])
        rapport.add(
            row=numero,
            column="is_staff",
            code="role_collaborateur",
            message="Colonne « Mitarbeiter » cochée : rôle collaborateur, non adhésion.",
        )

    if parse_bool(champs.get("is_board")):
        rapport.add(
            row=numero,
            column="is_board",
            code="categorie_a_arbitrer",
            message=(
                "Colonne « Vorstand » cochée, sans équivalent établi : contact importé "
                "sans adhésion de comité, correspondance à trancher."
            ),
            severity=Severity.REVIEW,
        )

    if not parse_bool(champs.get("is_supporter")):
        return

    type_adhesion = MembershipType.objects.filter(code="supporter").first()
    if type_adhesion is None:
        rapport.add(
            row=numero,
            column="is_supporter",
            code="type_absent",
            message="Type d'adhésion « supporter » absent : lancer `seed_reference`.",
            severity=Severity.ERROR,
        )
        return

    if contact.memberships.exists():
        return

    Membership.objects.create(
        contact=contact, type=type_adhesion, starts_on=depuis or DEBUT_INCONNU
    )
    if depuis is None:
        rapport.add(
            row=numero,
            column="since",
            code="date_adhesion_inconnue",
            message=(
                f"Date d'adhésion absente : début fixé au {DEBUT_INCONNU:%d.%m.%Y}, à corriger."
            ),
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
