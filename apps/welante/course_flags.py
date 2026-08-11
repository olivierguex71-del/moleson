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
from apps.welante.corrections import corriger_intitule


def _forme_comparable(valeur: str) -> str:
    """Forme de comparaison : sans accent, sans ponctuation, en minuscules.

    « Cours Privés & Entreprises » devient « cours prives entreprises » : c'est
    cette fonction, et non une transcription faite à la main, qui doit produire
    les clés des tables ci-dessous — sans quoi une esperluette ou un accent
    suffit à rendre une correspondance inatteignable.
    """
    return slugify(valeur).replace("-", " ")


def _table(correspondances: dict) -> dict:
    """Normalise les clés d'une table de correspondance."""
    return {_forme_comparable(intitule): valeur for intitule, valeur in correspondances.items()}


#: Les cours et l'écran des catégories n'emploient pas toujours la même forme :
#: la catégorie s'appelle « Highlight », les cours la citent au pluriel.
ETIQUETTES = _table(
    {
        "Newsletter": "in_newsletter",
        "Newsletters": "in_newsletter",
        "Highlight": "is_highlight",
        "Highlights": "is_highlight",
        "Cours à démarrage garanti": "has_guaranteed_start",
        "Démarrage garanti": "has_guaranteed_start",
        "sur demande": "is_on_demand",
    }
)

#: Catégorie administrative → valeur du champ `administrative_type`.
TYPES = _table(
    {
        "ORS": AdministrativeType.ORS,
        "Formation interne": AdministrativeType.INTERNAL,
        "Cours Privés & Entreprises": AdministrativeType.CORPORATE,
        "Cours privés et entreprises": AdministrativeType.CORPORATE,
        "Cours privés": AdministrativeType.CORPORATE,
    }
)


def appliquer_categories(cours, categories: list[str]) -> tuple[list[Subject], list[str]]:
    """Applique les catégories d'une ligne à un cours.

    Renvoie les matières reconnues et les intitulés restés sans correspondance,
    que l'appelant signalera dans son rapport.
    """
    matieres: list[Subject] = []
    inconnues: list[str] = []
    modifie: list[str] = []

    for brute in categories:
        # Une catégorie de cours peut être hiérarchique : « ORS > ORS - Français ».
        # Le régime administratif se lit sur le premier niveau, la matière sur le
        # dernier. Ne comparer que l'intitulé entier laissait passer les six
        # cours ORS de l'export, sans que rien ne le signale.
        entier = _forme_comparable(brute)
        premier_niveau = _forme_comparable(brute.split(">")[0])

        if champ := ETIQUETTES.get(entier) or ETIQUETTES.get(premier_niveau):
            setattr(cours, champ, True)
            modifie.append(champ)
            continue

        if type_administratif := TYPES.get(entier) or TYPES.get(premier_niveau):
            cours.administrative_type = type_administratif
            modifie.append("administrative_type")
            # Un cours ORS reste classé dans la matière « ORS - Français » :
            # le régime administratif et le classement ne s'excluent pas.
            if matiere := _trouver_matiere(brute):
                matieres.append(matiere)
            continue

        if matiere := _trouver_matiere(brute):
            matieres.append(matiere)
        else:
            inconnues.append(brute)

    if modifie:
        cours.save(update_fields=sorted(set(modifie)))

    return matieres, inconnues


def _trouver_matiere(intitule: str) -> Subject | None:
    """Retrouve une matière par son dernier niveau (« Parent > Enfant » → « Enfant »).

    La même correction de coquille qu'à l'import des catégories est appliquée :
    sans elle, un cours classé « Informatique & Technonolgie » ne retrouverait
    pas la matière enregistrée sous son intitulé corrigé.
    """
    dernier = corriger_intitule(intitule.split(">")[-1].strip())
    return (
        Subject.objects.filter(slug=slugify(dernier)[:60]).first()
        or Subject.objects.filter(name_fr__iexact=dernier).first()
        or Subject.objects.filter(name_de__iexact=dernier).first()
    )
