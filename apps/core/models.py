"""Briques transverses des modèles Moléson."""

from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


def content_language(language: str | None = None) -> str:
    """Normalise une langue vers l'une des deux langues de contenu (`fr` ou `de`).

    Accepte `None` (langue active de la requête), les variantes régionales
    (`de-ch` → `de`) et retombe sur la langue par défaut pour tout le reste.
    """
    language = language or get_language() or settings.LANGUAGE_CODE
    base = language.split("-")[0].lower()
    return base if base in settings.CONTENT_LANGUAGES else settings.LANGUAGE_CODE


class TimeStampedModel(models.Model):
    """Horodatage de création et de modification, sur toutes les entités."""

    created_at = models.DateTimeField(_("créé le"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        abstract = True


class TranslatedFieldsMixin:
    """Accès uniforme aux champs bilingues `<nom>_fr` / `<nom>_de`.

    Moléson stocke chaque contenu utilisateur dans deux colonnes explicites
    (`title_fr`, `title_de`) plutôt que dans un JSON ou une table de traductions :
    les colonnes restent indexables, interrogeables et lisibles en SQL brut.
    Ce mixin n'ajoute aucun champ — il ne fournit que la lecture par langue.

    Ne jamais concaténer les deux langues dans un même champ : c'est l'anti-pattern
    Welante que ce projet corrige.
    """

    def tr(self, field_name: str, language: str | None = None, *, fallback: bool = True) -> str:
        """Renvoie `<field_name>` dans la langue demandée.

        Avec `fallback` (par défaut), une valeur vide dans la langue demandée est
        remplacée par l'autre langue — mieux vaut un titre en allemand qu'un vide
        sur une page française. Passer `fallback=False` pour détecter les
        traductions manquantes (contrôles de complétude, écrans de saisie).
        """
        language = content_language(language)
        value = getattr(self, f"{field_name}_{language}", "") or ""
        if value or not fallback:
            return value
        for other in settings.CONTENT_LANGUAGES:
            if other == language:
                continue
            if alternative := (getattr(self, f"{field_name}_{other}", "") or ""):
                return alternative
        return ""

    def missing_translations(self, *field_names: str) -> list[str]:
        """Liste les champs `<nom>_<langue>` vides parmi ceux demandés.

        Sert aux contrôles de complétude avant publication d'un cours.
        """
        return [
            f"{field_name}_{language}"
            for field_name in field_names
            for language in settings.CONTENT_LANGUAGES
            if not (getattr(self, f"{field_name}_{language}", "") or "").strip()
        ]
