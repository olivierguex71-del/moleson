"""Résolution des colonnes d'un export Welante.

Les intitulés de colonnes varient d'un export à l'autre : accents, casse,
abréviations, langue, et parfois un intitulé bilingue. Les comparer à
l'identique casserait au premier export légèrement différent.

Chaque colonne attendue est donc décrite par un nom canonique et une liste
d'intitulés possibles, tous comparés sous une forme normalisée. Une colonne
introuvable n'interrompt pas l'import : elle est signalée dans le rapport, ce
qui laisse voir d'un coup toutes les corrections à faire plutôt qu'une seule
par exécution.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from apps.welante.normalizers import clean_text


def normalize_header(intitule: object) -> str:
    """Ramène un intitulé de colonne à une forme comparable.

    « TN Min-Max » → ``tn_min_max``, « Catégorie » → ``categorie``,
    « Bank IBANname » → ``bank_ibanname``.
    """
    texte = str(intitule or "").strip().lower()
    # Les accents disparaissent : « Catégorie » et « Categorie » sont le même mot.
    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.combining(caractere)
    )
    texte = re.sub(r"[^a-z0-9]+", "_", texte)
    return texte.strip("_")


@dataclass(frozen=True)
class Column:
    """Une colonne attendue dans un export.

    L'ordre des alias est un **ordre de préférence** : le premier trouvé gagne.
    Il compte, car plusieurs colonnes plausibles coexistent souvent dans un même
    export — « Formateur/trice Bank IBANname », renseignée à 60 %, et « Banque »,
    renseignée à 1 %.
    """

    name: str
    aliases: tuple[str, ...] = ()
    required: bool = False
    note: str = ""

    @property
    def candidates(self) -> tuple[str, ...]:
        """Formes normalisées des intitulés acceptés, par ordre de préférence.

        Surtout pas un ensemble : Python randomise le hachage des chaînes d'un
        processus à l'autre, si bien qu'un ensemble ferait résoudre la même
        colonne différemment d'une exécution à la suivante. Une migration doit
        donner le même résultat à chaque passage.
        """
        formes: list[str] = []
        for intitule in (self.name, *self.aliases):
            forme = normalize_header(intitule)
            if forme and forme not in formes:
                formes.append(forme)
        return tuple(formes)


@dataclass
class ColumnMapping:
    """Correspondance entre colonnes attendues et colonnes réellement présentes."""

    resolved: dict[str, str] = field(default_factory=dict)
    missing: list[Column] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def missing_required(self) -> list[Column]:
        return [colonne for colonne in self.missing if colonne.required]

    def get(self, name: str) -> str | None:
        """Intitulé réel de la colonne canonique `name`, ou `None` si absente."""
        return self.resolved.get(name)


@dataclass(frozen=True)
class RowValues:
    """Lecture d'une ligne par nom canonique de colonne.

    Remplace une fermeture définie dans la boucle d'import : celle-ci capturait
    la variable de boucle, piège classique qui rendrait le code faux dès qu'un
    appel serait différé.
    """

    mapping: ColumnMapping
    row: object

    def get(self, name: str) -> str:
        """Valeur nettoyée de la colonne, ou chaîne vide si elle est absente."""
        colonne = self.mapping.get(name)
        return clean_text(self.row[colonne]) if colonne else ""


def resolve_columns(headers: list[str], expected: list[Column]) -> ColumnMapping:
    """Associe les colonnes attendues aux intitulés réellement présents."""
    par_forme_normalisee: dict[str, str] = {}
    for intitule in headers:
        par_forme_normalisee.setdefault(normalize_header(intitule), str(intitule))

    mapping = ColumnMapping()
    utilisees: set[str] = set()

    for colonne in expected:
        trouvee = next(
            (
                par_forme_normalisee[candidat]
                for candidat in colonne.candidates
                if candidat in par_forme_normalisee
            ),
            None,
        )
        if trouvee is None:
            mapping.missing.append(colonne)
        else:
            mapping.resolved[colonne.name] = trouvee
            utilisees.add(trouvee)

    mapping.unexpected = [str(intitule) for intitule in headers if str(intitule) not in utilisees]
    return mapping
