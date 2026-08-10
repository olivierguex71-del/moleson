"""Chiffrement applicatif des champs sensibles (nLPD).

Utilisé pour les numéros AVS des formateurs. Le chiffrement disque du VPS ne
suffit pas : il ne protège rien contre une fuite de sauvegarde ou un accès
lecture à la base. Le chiffrement se fait donc au niveau du champ, en amont de
PostgreSQL.

Trente lignes maîtrisées valent mieux qu'une dépendance tierce non maintenue sur
une donnée que la loi nous demande de protéger.

Contrepartie assumée : un champ chiffré n'est ni indexable ni interrogeable
(Fernet produit un chiffré différent à chaque appel). C'est acceptable pour un
No AVS, que l'on lit sur une fiche mais que l'on ne recherche jamais.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models


def _cipher() -> MultiFernet:
    """Construit le chiffreur à partir de `settings.MOLESON_ENCRYPTION_KEYS`.

    La première clé chiffre ; les suivantes ne servent qu'à déchiffrer
    l'existant, ce qui permet une rotation de clé sans interruption.
    """
    keys = [key.strip() for key in settings.MOLESON_ENCRYPTION_KEYS if key.strip()]
    if not keys:
        raise ImproperlyConfigured(
            "MOLESON_ENCRYPTION_KEYS est vide : impossible de lire ou d'écrire un champ "
            "chiffré. Générer une clé avec "
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"`.'
        )
    return MultiFernet([Fernet(key.encode()) for key in keys])


class EncryptedTextField(models.TextField):
    """Champ texte chiffré au repos, transparent à l'usage.

    En base : un jeton Fernet. En Python : la valeur en clair.
    """

    def get_prep_value(self, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        return _cipher().encrypt(str(value).encode()).decode()

    def from_db_value(self, value: str | None, expression, connection) -> str | None:
        if value is None or value == "":
            return value
        try:
            return _cipher().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            # Échouer bruyamment : rendre du charabia sur un No AVS serait pire
            # que s'arrêter. Cause la plus probable : clé absente de la rotation.
            raise ValueError(
                f"Déchiffrement impossible pour le champ « {self.name} » — la clé ayant "
                "servi au chiffrement manque-t-elle dans MOLESON_ENCRYPTION_KEYS ?"
            ) from exc

    def get_lookup(self, lookup_name: str):
        # Seul `isnull` a un sens : il porte sur la présence, pas sur le contenu.
        if lookup_name != "isnull":
            raise FieldError(
                f"{self.__class__.__name__} n'est pas interrogeable "
                f"(tentative de `{lookup_name}` sur `{self.name}`) : le chiffré diffère "
                "à chaque écriture. Filtrer sur un autre champ, ou en Python après lecture."
            )
        return super().get_lookup(lookup_name)
