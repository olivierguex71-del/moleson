"""Répartition des « catégories » Welante entre trois notions distinctes.

Un même champ mélange :

- des **matières** (« Cours de langues > Italien ») → relation vers `Subject` ;
- des **étiquettes marketing** (« Newsletter », « Highlight », « Cours à
  démarrage garanti », « sur demande ») → booléens du cours ;
- des **types administratifs** (« ORS », « Formation interne », « Cours privés &
  entreprises ») → attribut du cours.

Les distinguer n'est pas cosmétique : mêlées, elles rendaient impossible tout
filtrage fiable du catalogue, et obligeaient le secrétariat à cocher
« Newsletter » dans la même liste que « Italien ».
"""

from django.utils.text import slugify

from apps.catalog.models import AdministrativeType, Subject

#: Étiquette marketing → attribut booléen du cours.
ETIQUETTES = {
    "newsletter": "in_newsletter",
    "highlight": "is_highlight",
    "cours a demarrage garanti": "has_guaranteed_start",
    "demarrage garanti": "has_guaranteed_start",
    "sur demande": "is_on_demand",
}

#: Catégorie administrative → valeur du champ `administrative_type`.
TYPES = {
    "ors": AdministrativeType.ORS,
    "formation interne": AdministrativeType.INTERNAL,
    "cours prives & entreprises": AdministrativeType.CORPORATE,
    "cours prives et entreprises": AdministrativeType.CORPORATE,
    "cours prives": AdministrativeType.CORPORATE,
}


def _forme_comparable(valeur: str) -> str:
    return slugify(valeur).replace("-", " ")


def appliquer_categories(cours, categories: list[str]) -> tuple[list[Subject], list[str]]:
    """Applique les catégories d'une ligne à un cours.

    Renvoie les matières reconnues et les intitulés restés sans correspondance,
    que l'appelant signalera dans son rapport.
    """
    matieres: list[Subject] = []
    inconnues: list[str] = []
    modifie: list[str] = []

    for brute in categories:
        forme = _forme_comparable(brute)

        if champ := ETIQUETTES.get(forme):
            setattr(cours, champ, True)
            modifie.append(champ)
            continue

        if type_administratif := TYPES.get(forme):
            cours.administrative_type = type_administratif
            modifie.append("administrative_type")
            continue

        if matiere := _trouver_matiere(brute):
            matieres.append(matiere)
        else:
            inconnues.append(brute)

    if modifie:
        cours.save(update_fields=sorted(set(modifie)))

    return matieres, inconnues


def _trouver_matiere(intitule: str) -> Subject | None:
    """Retrouve une matière par son dernier niveau (« Parent > Enfant » → « Enfant »)."""
    dernier = intitule.split(">")[-1].strip()
    return (
        Subject.objects.filter(slug=slugify(dernier)[:60]).first()
        or Subject.objects.filter(name_fr__iexact=dernier).first()
        or Subject.objects.filter(name_de__iexact=dernier).first()
    )
