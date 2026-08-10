"""Import des cours.

Le cœur de la migration, et l'endroit où trois anti-patterns se défont :

- **titre et descriptif** contiennent l'allemand et le français concaténés — ils
  repartent dans `title_fr` / `title_de`, avec relecture des cas douteux ;
- les **catégories** mêlent matières, étiquettes marketing et types
  administratifs — chacune retrouve sa place ;
- la colonne **« Chiffre »** est un artefact d'export (la dernière lettre du
  suffixe régional, mal découpée par Welante) : elle est ignorée, la région étant
  lue dans le code de cours.
"""

from django.utils.text import slugify

from apps.catalog.course_codes import parse_course_code
from apps.catalog.models import AdministrativeType, Course, CourseStatus, Subject
from apps.welante.columns import ColumnMapping, RowValues
from apps.welante.course_flags import appliquer_categories
from apps.welante.importers.base import ensure_period, resolve_region
from apps.welante.language import split_bilingual
from apps.welante.normalizers import parse_decimal, parse_int_range, split_multi
from apps.welante.reports import ImportReport, Severity, ligne_isolee
from apps.welante.workbook import Workbook

#: Les sept statuts observés dans l'export réel. Welante mêle l'état du cours et
#: l'avancement du travail administratif ; Moléson ne retient que le premier.
#: « Contrôler » et « En cours de traitement » décrivent une tâche du secrétariat,
#: pas un cours publiable : ils deviennent des brouillons.
STATUTS_WELANTE = {
    "annule": CourseStatus.CANCELLED,
    "effectue": CourseStatus.COMPLETED,
    "courant": CourseStatus.PUBLISHED,
    "inscription": CourseStatus.PUBLISHED,
    "pret": CourseStatus.PUBLISHED,
    "controler": CourseStatus.DRAFT,
    "en cours de traitement": CourseStatus.DRAFT,
}


def import_courses(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
    rapport = ImportReport(source=classeur.path.name)

    colonne_code = mapping.get("code")
    colonne_titre = mapping.get("title")
    if not colonne_code or not colonne_titre:
        rapport.add(
            row=1,
            column="code",
            code="colonne_manquante",
            message="Colonnes du code ou du titre introuvables : import impossible.",
            severity=Severity.ERROR,
        )
        return rapport

    if mapping.get("digit"):
        rapport.add(
            row=1,
            column="digit",
            code="colonne_ignoree",
            message="Colonne « Chiffre » ignorée : artefact d'export, la région vient du code.",
        )
    for colonne_statistique in ("women_share", "age"):
        if mapping.get(colonne_statistique):
            rapport.add(
                row=1,
                column=colonne_statistique,
                code="statistique_non_migree",
                message="Statistique dérivée des inscriptions : recalculée, jamais stockée.",
            )

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1
        with ligne_isolee(rapport, numero):
            champs = RowValues(mapping, ligne)

            code = champs.get("code")
            if not code:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="code",
                    code="code_absent",
                    message="Cours sans code : ligne non importable.",
                    severity=Severity.ERROR,
                )
                continue

            composants = parse_course_code(code)
            if composants is None:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="code",
                    code="code_herite",
                    message=(
                        "Code au format antérieur à 2023 : période et région indéterminables, "
                        "à rattacher à la main."
                    ),
                    severity=Severity.REVIEW,
                )
                continue

            region = resolve_region(composants.region, report=rapport, row=numero)
            if region is None:
                rapport.rows_skipped += 1
                continue

            periode = ensure_period(
                year=composants.year, kind=composants.period, report=rapport, row=numero
            )

            titre = split_bilingual(champs.get("title"))
            descriptif = split_bilingual(champs.get("description"))
            for champ, decoupage in (("title", titre), ("description", descriptif)):
                if decoupage.needs_review and decoupage.strategy != "champ vide":
                    rapport.add(
                        row=numero,
                        column=champ,
                        code="decoupage_a_relire",
                        message=decoupage.review_reason,
                        severity=Severity.REVIEW,
                    )

            prix = parse_decimal(champs.get("price"))
            if prix is None:
                rapport.add(
                    row=numero,
                    column="price",
                    code="prix_illisible",
                    message="Prix absent ou illisible : cours importé à 0 CHF, à corriger.",
                    severity=Severity.REVIEW,
                )
            minimum, maximum = parse_int_range(champs.get("participants"))

            cours, cree = Course.objects.get_or_create(
                code=code,
                defaults={
                    "period": periode,
                    "region": region,
                    "title_fr": titre.fr,
                    "title_de": titre.de,
                    "description_fr": descriptif.fr,
                    "description_de": descriptif.de,
                    "base_price": prix or 0,
                    "min_participants": minimum,
                    "max_participants": maximum,
                    "status": _statut(champs.get("status"), rapport, numero),
                    "administrative_type": AdministrativeType.STANDARD,
                    "legacy_reference": code,
                },
            )
            if not cree:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="code",
                    code="cours_deja_importe",
                    message="Un cours porte déjà ce code : ligne ignorée.",
                )
                continue

            _rattacher_categories(cours, split_multi(champs.get("categories")), rapport, numero)
            rapport.rows_imported += 1

    return rapport


def _statut(brut: str, rapport: ImportReport, numero: int) -> str:
    """Traduit le statut Welante, ou range en brouillon si l'intitulé est inconnu.

    Publier par défaut serait le mauvais réflexe : mieux vaut un cours à publier
    à la main qu'un cours mis en ligne par accident.
    """
    forme = slugify(brut).replace("-", " ")
    if not forme:
        return CourseStatus.DRAFT
    if statut := STATUTS_WELANTE.get(forme):
        return statut

    rapport.add(
        row=numero,
        column="status",
        code="statut_inconnu",
        message=f"Statut « {brut} » non reconnu : cours importé en brouillon.",
        severity=Severity.REVIEW,
    )
    return CourseStatus.DRAFT


def _rattacher_categories(cours, categories: list[str], rapport: ImportReport, numero: int) -> None:
    """Range chaque catégorie où elle doit aller : matière, étiquette ou type."""
    matieres, inconnues = appliquer_categories(cours, categories)

    if matieres:
        cours.subjects.set(Subject.objects.filter(slug__in=[m.slug for m in matieres]))

    for inconnue in inconnues:
        rapport.add(
            row=numero,
            column="categories",
            code="matiere_inconnue",
            message=(
                f"Catégorie « {inconnue} » absente de la taxonomie : "
                "importer les catégories d'abord, ou la créer."
            ),
            severity=Severity.REVIEW,
        )
