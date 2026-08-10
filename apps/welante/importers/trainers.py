"""Import des intervenant-e-s.

Deux points sensibles :

- le **numéro AVS** est chiffré dès l'écriture par `EncryptedTextField` — rien à
  faire ici sinon ne jamais le recopier dans un rapport ou un journal ;
- l'**IBAN** est normalisé et vérifié par sa clé de contrôle. Un IBAN faux est
  écarté plutôt qu'importé : c'est un virement de formateur qui se perdrait.

Les quinze colonnes de questionnaire FIDE présentes dans l'export ne sont pas
migrées : des réponses de formulaire n'ont pas à devenir des colonnes de contact.
"""

from apps.contacts.models import Trainer
from apps.welante.columns import ColumnMapping, RowValues
from apps.welante.importers.base import ContactResolver
from apps.welante.normalizers import normalize_iban_value, parse_bool
from apps.welante.reports import ImportReport, Severity
from apps.welante.workbook import Workbook


#: Codes BIC glissés dans la colonne « Bank IBANname », mêlés aux noms de banque.
def _est_un_bic(valeur: str) -> bool:
    return len(valeur) in (8, 11) and valeur.isalnum() and valeur.isupper()


def import_trainers(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
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

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1

        champs = RowValues(mapping, ligne)

        contact = resolveur.resolve(
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
            },
        )
        if contact is None:
            rapport.rows_skipped += 1
            continue

        iban, motif = normalize_iban_value(champs.get("iban"))
        if motif and motif != "absent":
            rapport.add(
                row=numero,
                column="iban",
                code=f"iban_{motif}",
                message="IBAN écarté : clé de contrôle ou forme invalide. À ressaisir.",
                severity=Severity.REVIEW,
            )

        banque = champs.get("bank")
        bic = banque if _est_un_bic(banque) else ""
        if bic:
            rapport.add(
                row=numero,
                column="bank",
                code="bic_dans_nom_de_banque",
                message="La colonne « Bank IBANname » contenait un BIC : rangé comme tel.",
            )

        formateur, cree = Trainer.objects.get_or_create(
            contact=contact,
            defaults={
                "iban": iban or "",
                "bic": bic,
                "bank_name": "" if bic else banque,
                "ahv_number": champs.get("ahv_number"),
                "ahv_waiver": parse_bool(champs.get("ahv_waiver")),
            },
        )
        if not cree:
            rapport.add(
                row=numero,
                column="last_name",
                code="formateur_deja_importe",
                message="Un profil de formateur existait déjà pour ce contact : ligne ignorée.",
            )
            rapport.rows_skipped += 1
            continue

        if formateur.ahv_number:
            rapport.add(
                row=numero,
                column="ahv_number",
                code="avs_chiffre",
                message="Numéro AVS chiffré au repos ; accès réservé et exclu des exports.",
            )

        rapport.rows_imported += 1

    return rapport
