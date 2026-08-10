"""Import de la taxonomie.

Trois concepts sortent d'un même écran Welante et doivent être séparés :
la **taxonomie** (matières), les **étiquettes** marketing (Newsletter, Highlight,
démarrage garanti, sur demande) et les **types administratifs** (ORS, formation
interne, cours privés). Seules les matières deviennent des `Subject` ; les autres
sont reconnues et écartées, en le disant.
"""

from django.utils.text import slugify

from apps.catalog.models import Subject
from apps.welante.columns import ColumnMapping
from apps.welante.language import split_bilingual
from apps.welante.normalizers import clean_text, parse_category_path, parse_int
from apps.welante.reports import ImportReport, Severity, ligne_isolee
from apps.welante.workbook import Workbook

#: Entrées de l'écran « Catégories » qui n'en sont pas.
ETIQUETTES_MARKETING = {"newsletter", "highlight", "cours a demarrage garanti", "sur demande"}
TYPES_ADMINISTRATIFS = {"ors", "formation interne", "cours prives & entreprises", "cours prives"}

#: Coquille présente dans les données sources.
CORRECTIONS = {"Informatique & Technonolgie": "Informatique & Technologie"}


def _forme_comparable(nom: str) -> str:
    return slugify(nom).replace("-", " ")


def import_categories(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
    """Crée les matières, sur deux niveaux, en préservant les Web-Codes."""
    rapport = ImportReport(source=classeur.path.name)
    colonne_nom = mapping.get("name")
    if not colonne_nom:
        rapport.add(
            row=1,
            column="name",
            code="colonne_manquante",
            message="Colonne du nom de catégorie introuvable : import impossible.",
            severity=Severity.ERROR,
        )
        return rapport

    colonne_code = mapping.get("web_code")
    colonne_parent = mapping.get("parent")
    colonne_position = mapping.get("position")

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1
        with ligne_isolee(rapport, numero):
            brut = clean_text(ligne[colonne_nom])
            if not brut:
                rapport.rows_skipped += 1
                continue

            nom = CORRECTIONS.get(brut, brut)
            if nom != brut:
                rapport.add(
                    row=numero,
                    column="name",
                    code="coquille_corrigee",
                    message="Coquille connue corrigée automatiquement.",
                )

            comparable = _forme_comparable(nom)
            if comparable in ETIQUETTES_MARKETING:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="name",
                    code="etiquette_marketing",
                    message="Étiquette marketing, non migrée en matière (flag sur le cours).",
                )
                continue
            if comparable in TYPES_ADMINISTRATIFS:
                rapport.rows_skipped += 1
                rapport.add(
                    row=numero,
                    column="name",
                    code="type_administratif",
                    message="Type administratif, non migré en matière (attribut du cours).",
                )
                continue

            parent_nom, enfant_nom = parse_category_path(nom)
            if colonne_parent and (declare := clean_text(ligne[colonne_parent])):
                parent_nom, enfant_nom = declare, nom

            parent = None
            if enfant_nom:
                parent = _creer_matiere(parent_nom, None, None, rapport, numero)

            nom_final = enfant_nom or parent_nom
            code_web = clean_text(ligne[colonne_code]) if colonne_code else ""
            if not code_web:
                rapport.add(
                    row=numero,
                    column="web_code",
                    code="web_code_absent",
                    message=(
                        "Sans Web-Code : un identifiant est dérivé du nom, l'URL du site changera."
                    ),
                    severity=Severity.REVIEW,
                )

            matiere = _creer_matiere(nom_final, code_web, parent, rapport, numero)
            if colonne_position and (position := parse_int(ligne[colonne_position])) is not None:
                matiere.position = position
                matiere.save(update_fields=["position"])

            rapport.rows_imported += 1

    return rapport


def _creer_matiere(nom, code_web, parent, rapport: ImportReport, numero: int) -> Subject:
    """Crée ou retrouve une matière, en découpant son intitulé bilingue."""
    decoupage = split_bilingual(nom)
    slug = code_web or slugify(nom)[:60]

    matiere, cree = Subject.objects.get_or_create(
        slug=slug,
        defaults={
            "name_fr": decoupage.fr or nom,
            "name_de": decoupage.de,
            "parent": parent,
        },
    )
    if cree and decoupage.needs_review and decoupage.strategy != "champ vide":
        rapport.add(
            row=numero,
            column="name",
            code="decoupage_a_relire",
            message=decoupage.review_reason,
            severity=Severity.REVIEW,
        )
    return matiere
