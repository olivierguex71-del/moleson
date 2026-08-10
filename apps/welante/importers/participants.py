"""Import des inscriptions.

Une ligne d'export = une inscription, pas un contact : les 28 contacts répétés
de l'export ne sont pas des doublons mais des personnes inscrites à plusieurs
cours. C'est exactement la séparation contact / inscription que Moléson établit,
et que Welante ne faisait pas.

Le statut source ne connaît qu'une valeur, « Copié », qui dit qu'une inscription
a été recopiée du trimestre précédent — sans dire si la personne avait confirmé.
Les inscriptions sont donc importées comme confirmées, puisqu'elles figurent au
programme, et l'ambiguïté est consignée.
"""

from apps.catalog.models import Course
from apps.enrolments.models import Enrolment, EnrolmentSource, EnrolmentStatus
from apps.welante.columns import ColumnMapping, RowValues
from apps.welante.importers.base import ContactResolver
from apps.welante.normalizers import clean_text, parse_date, parse_decimal
from apps.welante.reports import ImportReport, Severity, ligne_isolee
from apps.welante.workbook import Workbook


def import_participants(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
    rapport = ImportReport(source=classeur.path.name)
    resolveur = ContactResolver(report=rapport)

    colonne_cours = mapping.get("course_code")
    if not mapping.get("last_name") or not colonne_cours:
        rapport.add(
            row=1,
            column="course_code",
            code="colonne_manquante",
            message="Colonnes du nom ou du cours introuvables : import impossible.",
            severity=Severity.ERROR,
        )
        return rapport

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1
        with ligne_isolee(rapport, numero):
            champs = RowValues(mapping, ligne)

            code_cours = champs.get("course_code")
            cours = Course.objects.filter(code=code_cours).first()
            if cours is None:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="course_code",
                    code="cours_introuvable",
                    message=(
                        f"Aucun cours au code « {code_cours} » : importer les cours d'abord, "
                        "ou corriger le code."
                    ),
                    severity=Severity.ERROR,
                )
                continue

            participant = resolveur.resolve(
                row=numero,
                donnees={
                    "last_name": champs.get("last_name"),
                    "first_name": champs.get("first_name"),
                    "email": champs.get("email"),
                    "phone": champs.get("phone"),
                    "mobile": champs.get("mobile"),
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
            if participant is None:
                rapport.rows_skipped += 1
                continue

            payeur = _resoudre_payeur(champs.get("billing_contact"), resolveur, numero, rapport)

            if Enrolment.objects.filter(course=cours, participant=participant).exists():
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="course_code",
                    code="inscription_en_double",
                    message="Cette personne est déjà inscrite à ce cours : ligne ignorée.",
                )
                continue

            statut = clean_text(champs.get("status")).lower()
            if statut:
                rapport.add(
                    row=numero,
                    column="status",
                    code="statut_ambigu",
                    message=(
                        "Le statut source ne distingue pas proposé et confirmé : "
                        "inscription importée comme confirmée."
                    ),
                )

            inscription = Enrolment.objects.create(
                course=cours,
                participant=participant,
                billing_contact=payeur,
                status=EnrolmentStatus.CONFIRMED,
                source=EnrolmentSource.IMPORT,
                enrolled_on=parse_date(champs.get("created")) or cours.period.starts_on,
                notes=champs.get("notes"),
                legacy_reference=code_cours,
            )

            _reporter_prix(inscription, champs.get("price"), rapport, numero)
            rapport.rows_imported += 1

    return rapport


def _resoudre_payeur(brut: str, resolveur: ContactResolver, numero: int, rapport: ImportReport):
    """Crée le contact de facturation quand il diffère du participant.

    Huit cas dans l'export — employeur, proche. Le champ est du texte libre : on
    ne sait en tirer qu'un nom, le reste de la fiche est à compléter.
    """
    nom = clean_text(brut)
    if not nom:
        return None

    rapport.add(
        row=numero,
        column="billing_contact",
        code="payeur_a_completer",
        message=(
            "Contact de facturation créé depuis un texte libre : adresse et "
            "courriel à compléter avant toute facturation."
        ),
        severity=Severity.REVIEW,
    )
    return resolveur.resolve(row=numero, donnees={"last_name": "", "organisation": nom})


def _reporter_prix(inscription, brut: str, rapport: ImportReport, numero: int) -> None:
    """Conserve un prix qui s'écarte du tarif calculé, comme prix imposé."""
    montant = parse_decimal(brut)
    if montant is None:
        return
    if montant == inscription.price:
        return

    inscription.price_override = montant
    inscription.save(update_fields=["price_override"])
    rapport.add(
        row=numero,
        column="price",
        code="prix_impose_repris",
        message=(
            "Le montant facturé diffère du tarif calculé : repris comme prix imposé, "
            "à vérifier (promotion ? rabais oublié ?)."
        ),
        severity=Severity.REVIEW,
    )
