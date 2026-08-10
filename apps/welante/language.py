"""Séparation des contenus bilingues concaténés.

Welante range le titre et le descriptif d'un cours **allemand et français mêlés
dans un seul champ**. C'est l'anti-pattern que Moléson corrige : chaque contenu
doit repartir dans `title_fr` / `title_de`.

Le découpage automatique ne prétend pas être sûr. Il produit une proposition
**et un score de confiance**, et tout ce qui n'est pas franchement tranché part
en relecture humaine. Sur des textes de catalogue, un découpage faux est pire
qu'un découpage refusé : il passerait inaperçu jusqu'à la publication.

Aucune bibliothèque de détection de langue : sur du vocabulaire de catalogue en
deux langues connues d'avance, quelques dizaines de mots-outils font mieux qu'un
modèle général, sans dépendance à maintenir dix ans.
"""

import re
from dataclasses import dataclass

#: Mots grammaticaux — ils portent la langue bien mieux que le vocabulaire, qui
#: se ressemble souvent d'une langue à l'autre (« sport », « yoga », « test »).
MOTS_FR = {
    "le",
    "la",
    "les",
    "des",
    "du",
    "de",
    "un",
    "une",
    "et",
    "ou",
    "pour",
    "avec",
    "vous",
    "nous",
    "dans",
    "sur",
    "est",
    "sont",
    "plus",
    "cours",
    "ce",
    "cette",
    "aux",
    "par",
    "en",
    "au",
    "qui",
    "que",
    "votre",
    "notre",
    "sans",
    "chaque",
    "leurs",
    "vos",
    "nos",
    "afin",
    "ainsi",
    "aussi",
    "tous",
    "toutes",
    "être",
    "avoir",
    "faire",
    "niveau",
    "débutant",
    "séance",
    "séances",
    "inscription",
}

MOTS_DE = {
    "der",
    "die",
    "das",
    "den",
    "dem",
    "des",
    "und",
    "oder",
    "mit",
    "für",
    "sie",
    "wir",
    "ist",
    "sind",
    "ein",
    "eine",
    "einen",
    "im",
    "auf",
    "von",
    "zu",
    "kurs",
    "sich",
    "nicht",
    "auch",
    "werden",
    "wird",
    "haben",
    "sein",
    "bei",
    "aus",
    "über",
    "unter",
    "durch",
    "kann",
    "können",
    "ihre",
    "unsere",
    "jede",
    "jeden",
    "stufe",
    "anfänger",
    "lektion",
    "lektionen",
    "anmeldung",
}

#: Lettres qui ne mentent pas quand elles apparaissent.
LETTRES_DE = set("ßäöüÄÖÜ")
LETTRES_FR = set("àâçèéêëîïôùûœÀÂÇÈÉÊËÎÏÔÙÛŒ")

#: Séparateurs explicites parfois utilisés dans les exports.
SEPARATEURS = [
    "\n\n",
    " / ",
    " | ",
    " - - ",
    "---",
    "***",
    " // ",
]

#: En deçà, la proposition part systématiquement en relecture humaine.
SEUIL_DE_CONFIANCE = 0.75


@dataclass(frozen=True)
class LanguageScore:
    """Langue supposée d'un fragment, et à quel point elle est sûre."""

    language: str
    confidence: float

    @property
    def is_certain(self) -> bool:
        return self.confidence >= SEUIL_DE_CONFIANCE


def detect_language(texte: str) -> LanguageScore:
    """Devine si un fragment est français ou allemand.

    Renvoie une confiance nulle sur un texte trop court pour trancher — un titre
    de deux mots ne contient souvent aucun indice grammatical.
    """
    if not texte or not texte.strip():
        return LanguageScore("", 0.0)

    mots = re.findall(r"[\wàâçèéêëîïôùûœäöüßÀÂÇÈÉÊËÎÏÔÙÛŒÄÖÜ]+", texte.lower())
    if not mots:
        return LanguageScore("", 0.0)

    score_fr = sum(1 for mot in mots if mot in MOTS_FR)
    score_de = sum(1 for mot in mots if mot in MOTS_DE)

    # Les lettres propres à une langue valent un demi-point : moins décisives
    # qu'un mot-outil, mais elles sauvent les textes courts.
    score_de += 0.5 * sum(1 for caractere in texte if caractere in LETTRES_DE)
    score_fr += 0.5 * sum(1 for caractere in texte if caractere in LETTRES_FR)

    total = score_fr + score_de
    if total == 0:
        return LanguageScore("", 0.0)

    if score_fr >= score_de:
        return LanguageScore("fr", score_fr / total)
    return LanguageScore("de", score_de / total)


@dataclass(frozen=True)
class BilingualSplit:
    """Proposition de découpage d'un champ bilingue."""

    fr: str
    de: str
    confidence: float
    strategy: str
    needs_review: bool

    @property
    def is_complete(self) -> bool:
        return bool(self.fr.strip() and self.de.strip())

    @property
    def review_reason(self) -> str:
        """Motif de relecture, formulé pour être compris sans connaître l'algorithme.

        Deux situations très différentes se cachent derrière « à relire » : un
        champ qui ne contenait qu'une langue — la confiance dans la détection
        peut alors être totale, il manque simplement l'autre version — et un
        découpage réellement incertain.
        """
        if not self.needs_review:
            return ""
        if self.strategy == "langue indéterminée":
            # Le texte a été rangé en français faute de mieux : ce n'est pas une
            # détection, et le dire autrement induirait le relecteur en erreur.
            return (
                "Langue indéterminée : contenu placé en français par défaut, "
                "à répartir entre les deux langues."
            )
        if not self.is_complete:
            langue = "français" if self.fr.strip() else "allemand"
            return f"Une seule langue détectée ({langue}) : l'autre version reste à saisir."
        return f"Découpage FR/DE incertain ({self.strategy}, confiance {self.confidence:.0%})."


def _split_on_separator(texte: str) -> tuple[str, str, str] | None:
    """Coupe sur un séparateur explicite, en deux morceaux seulement."""
    for separateur in SEPARATEURS:
        if texte.count(separateur) == 1:
            gauche, droite = texte.split(separateur)
            if gauche.strip() and droite.strip():
                return gauche.strip(), droite.strip(), f"séparateur « {separateur.strip()} »"
    return None


def _segments(texte: str) -> list[str]:
    """Découpe en lignes, ou en phrases si le texte tient sur une ligne."""
    lignes = [ligne.strip() for ligne in texte.splitlines() if ligne.strip()]
    if len(lignes) > 1:
        return lignes
    phrases = [phrase.strip() for phrase in re.split(r"(?<=[.!?])\s+", texte) if phrase.strip()]
    return phrases or [texte.strip()]


def _split_on_language_shift(texte: str) -> tuple[str, str, str, float] | None:
    """Cherche le point où le texte bascule d'une langue à l'autre.

    Essaie chaque coupure possible entre segments et retient celle qui sépare le
    mieux les deux langues. Sans bascule nette, renvoie `None` plutôt qu'une
    coupure arbitraire.
    """
    segments = _segments(texte)
    if len(segments) < 2:
        return None

    scores = [detect_language(segment) for segment in segments]
    meilleure = None

    for coupure in range(1, len(segments)):
        avant, apres = scores[:coupure], scores[coupure:]
        for langue_avant, langue_apres in (("de", "fr"), ("fr", "de")):
            accords = sum(1 for score in avant if score.language == langue_avant)
            accords += sum(1 for score in apres if score.language == langue_apres)
            qualite = accords / len(segments)
            if meilleure is None or qualite > meilleure[0]:
                meilleure = (
                    qualite,
                    coupure,
                    langue_avant,
                    langue_apres,
                )

    if meilleure is None:
        return None

    qualite, coupure, langue_avant, _ = meilleure
    bloc_avant = "\n".join(segments[:coupure])
    bloc_apres = "\n".join(segments[coupure:])
    if langue_avant == "de":
        return bloc_apres, bloc_avant, "bascule de langue", qualite
    return bloc_avant, bloc_apres, "bascule de langue", qualite


def split_bilingual(texte: str) -> BilingualSplit:
    """Propose un découpage français / allemand d'un champ concaténé."""
    texte = (texte or "").strip()
    if not texte:
        return BilingualSplit("", "", 0.0, "champ vide", needs_review=False)

    if resultat := _split_on_separator(texte):
        gauche, droite, strategie = resultat
        score_gauche = detect_language(gauche)
        score_droite = detect_language(droite)
        if score_gauche.language == "de" or score_droite.language == "fr":
            fr, de = droite, gauche
        else:
            fr, de = gauche, droite
        confiance = min(score_gauche.confidence, score_droite.confidence)
        return BilingualSplit(
            fr=fr,
            de=de,
            confidence=confiance,
            strategy=strategie,
            needs_review=confiance < SEUIL_DE_CONFIANCE,
        )

    if resultat := _split_on_language_shift(texte):
        fr, de, strategie, qualite = resultat
        return BilingualSplit(
            fr=fr,
            de=de,
            confidence=qualite,
            strategy=strategie,
            needs_review=qualite < SEUIL_DE_CONFIANCE,
        )

    # Aucune bascule : le champ est probablement monolingue. On le range dans la
    # langue détectée et on laisse l'autre vide, à compléter à la main.
    score = detect_language(texte)
    if score.language == "de":
        return BilingualSplit(
            fr="",
            de=texte,
            confidence=score.confidence,
            strategy="texte unique (DE)",
            needs_review=True,
        )
    return BilingualSplit(
        fr=texte,
        de="",
        confidence=score.confidence,
        strategy="texte unique (FR)" if score.language else "langue indéterminée",
        needs_review=True,
    )
