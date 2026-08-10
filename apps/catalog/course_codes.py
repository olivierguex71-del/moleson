"""Lecture et écriture des codes de cours.

Format canonique : ``AAAA-Px-NNNNNN[v]-RG``

===========  ====================================================
``AAAA``     année
``Px``       période — T1 à T4 (trimestres), S1 ou S2 (semestres)
``NNNNNN``   identifiant, dont le préfixe désigne la matière
             (44xxxx anglais, 42xxxx italien, 72xxxx aquatique…)
``[v]``      variante, optionnelle (``421111b``)
``RG``       région — FR, GR, GL, SN
===========  ====================================================

Le suffixe est la **région**, pas la langue : l'erreur est facile et coûterait
une migration entière.

Les codes antérieurs à 2023 suivent d'autres formes (``1617-272-318``,
``2021-72-1021-SN``). Le code reste donc un champ libre : la région et la période
d'un cours sont portées par des clés étrangères, seule source de vérité. Le
parsing sert à contrôler la cohérence d'un code canonique, jamais à déduire les
données d'un cours.
"""

import re
from dataclasses import dataclass

_CODE_CANONIQUE = re.compile(
    r"""^
    (?P<year>\d{4})       -
    (?P<period>[TS]\d)    -
    (?P<number>\d{4,6})
    (?P<variant>[a-z]?)   -
    (?P<region>[A-Z]{2})
    $""",
    re.VERBOSE,
)


@dataclass(frozen=True)
class CourseCodeParts:
    """Composants d'un code de cours canonique."""

    year: int
    period: str
    number: str
    variant: str
    region: str

    @property
    def subject_prefix(self) -> str:
        """Deux premiers chiffres de l'identifiant : la famille de matières."""
        return self.number[:2]


def parse_course_code(code: str) -> CourseCodeParts | None:
    """Décompose un code canonique, ou renvoie `None` s'il ne l'est pas.

    Renvoyer `None` plutôt que lever : un code hérité de Welante n'est pas une
    erreur, seulement un code que l'on ne sait pas décomposer.
    """
    correspondance = _CODE_CANONIQUE.match((code or "").strip())
    if not correspondance:
        return None
    parts = correspondance.groupdict()
    return CourseCodeParts(
        year=int(parts["year"]),
        period=parts["period"],
        number=parts["number"],
        variant=parts["variant"],
        region=parts["region"],
    )


def build_course_code(
    *, year: int, period: str, number: str, region: str, variant: str = ""
) -> str:
    """Assemble un code canonique à partir de ses composants."""
    return f"{year}-{period}-{number}{variant}-{region}"


def is_canonical(code: str) -> bool:
    return parse_course_code(code) is not None
