"""Import de la taxonomie.

L'export se lit comme une **arborescence**, pas comme une liste : la catégorie
parente n'est écrite que sur sa propre ligne, et les lignes suivantes ne portent
que le nom de la sous-catégorie, dans une colonne sans en-tête. Traiter chaque
ligne isolément perdrait la moitié des entrées et toute la hiérarchie.

Trois concepts sortent par ailleurs de ce même écran Welante :

- la **taxonomie** (matières) — c'est elle qu'on importe ;
- les **étiquettes marketing** (Newsletter, Highlight, démarrage garanti, sur
  demande) — écartées, ce sont des booléens du cours ;
- les **types administratifs** (ORS, Formation interne, Cours privés) — gardés
  comme matières, car ce sont aussi des rubriques de classement : « ORS » porte
  deux sous-catégories linguistiques que l'écarter rendrait orphelines. Le type
  administratif du cours est déduit ailleurs, à partir de ses catégories.
"""

from django.utils.text import slugify

from apps.catalog.models import Subject
from apps.welante.columns import ColumnMapping, RowValues
from apps.welante.corrections import corriger_intitule
from apps.welante.language import split_bilingual
from apps.welante.normalizers import parse_bool, parse_category_path, parse_int
from apps.welante.reports import ImportReport, Severity, ligne_isolee
from apps.welante.workbook import Workbook

#: Entrées de l'écran « Catégories » qui n'en sont pas : elles deviennent des
#: booléens du cours. Aucune n'a de sous-catégorie.
ETIQUETTES_MARKETING = {
    "newsletter",
    "highlight",
    "cours a demarrage garanti",
    "demarrage garanti",
    "sur demande",
}


def _forme_comparable(nom: str) -> str:
    return slugify(nom).replace("-", " ")


def import_categories(classeur: Workbook, mapping: ColumnMapping) -> ImportReport:
    """Crée les matières sur deux niveaux, en préservant les Web-Codes."""
    rapport = ImportReport(source=classeur.path.name)
    if not mapping.get("name"):
        rapport.add(
            row=1,
            column="name",
            code="colonne_manquante",
            message="Colonne du nom de catégorie introuvable : import impossible.",
            severity=Severity.ERROR,
        )
        return rapport

    #: Dernière catégorie de premier niveau rencontrée : les lignes suivantes
    #: s'y rattachent tant qu'une nouvelle n'apparaît pas.
    parent_courant: Subject | None = None

    for numero, ligne in classeur.rows():
        rapport.rows_read += 1
        with ligne_isolee(rapport, numero):
            champs = RowValues(mapping, ligne)
            nom_parent = champs.get("name")
            nom_enfant = champs.get("child_name")

            if not nom_parent and not nom_enfant:
                rapport.rows_skipped += 1
                continue

            # Une hiérarchie peut aussi arriver sur une seule colonne, sous la
            # forme « Parent > Enfant » : les deux écritures coexistent.
            if nom_parent and not nom_enfant and ">" in nom_parent:
                nom_parent, nom_enfant = parse_category_path(nom_parent)

            actif = parse_bool(champs.get("show_on_web")) or not mapping.get("show_on_web")
            code_web = champs.get("web_code")

            if nom_parent:
                nom = _corriger(nom_parent, rapport, numero)
                if _forme_comparable(nom) in ETIQUETTES_MARKETING:
                    parent_courant = None
                    rapport.rows_skipped += 1
                    rapport.add(
                        row=numero,
                        column="name",
                        code="etiquette_marketing",
                        message="Étiquette marketing, non migrée en matière (flag du cours).",
                    )
                    continue
                parent_courant = _creer_matiere(nom, code_web, None, actif, rapport, numero, champs)
                if not nom_enfant:
                    rapport.rows_imported += 1
                    continue

            if not nom_enfant:
                continue

            if parent_courant is None:
                rapport.add(
                    row=numero,
                    column="child_name",
                    code="sous_categorie_orpheline",
                    message=(
                        "Sous-catégorie rencontrée avant toute catégorie parente : "
                        "créée au premier niveau, à reclasser."
                    ),
                    severity=Severity.REVIEW,
                )

            _creer_matiere(
                _corriger(nom_enfant, rapport, numero),
                code_web,
                parent_courant,
                actif,
                rapport,
                numero,
                champs,
            )
            rapport.rows_imported += 1

    return rapport


def _corriger(nom: str, rapport: ImportReport, numero: int) -> str:
    corrige = corriger_intitule(nom)
    if corrige != nom:
        rapport.add(
            row=numero,
            column="name",
            code="coquille_corrigee",
            message="Coquille connue corrigée automatiquement.",
        )
    return corrige


def _creer_matiere(nom, code_web, parent, actif, rapport, numero, champs) -> Subject:
    """Crée ou retrouve une matière, en découpant son intitulé bilingue."""
    decoupage = split_bilingual(nom)
    slug = code_web or slugify(nom)[:60]
    if not code_web:
        rapport.add(
            row=numero,
            column="web_code",
            code="web_code_absent",
            message="Sans Web-Code : identifiant dérivé du nom, l'URL du site changera.",
            severity=Severity.REVIEW,
        )

    matiere, cree = Subject.objects.get_or_create(
        slug=slug[:60],
        defaults={
            "name_fr": decoupage.fr or nom,
            "name_de": decoupage.de,
            "parent": parent,
            "is_active": actif,
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
    if position := parse_int(champs.get("position")):
        matiere.position = position
        matiere.save(update_fields=["position"])
    return matiere
