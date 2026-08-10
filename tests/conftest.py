"""Configuration commune des tests.

Règle nLPD non négociable : aucune donnée personnelle réelle dans les tests, les
fixtures, les seeds ou les journaux. Tout ce qui ressemble à un contact ici est
inventé.
"""

import pytest
from cryptography.fernet import Fernet
from django.test import Client


@pytest.fixture(autouse=True)
def static_files_without_manifest(settings):
    """Découple les tests de `collectstatic`.

    Le stockage « manifeste » de production exige un artefact de build ; les tests
    doivent passer sur un dépôt fraîchement cloné, quelle que soit la valeur de
    `DJANGO_DEBUG` dans le `.env` local.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture(autouse=True)
def encryption_keys(settings):
    """Fournit des clés de chiffrement jetables à tous les tests.

    Une paire de clés, pour que les tests de rotation aient de quoi travailler.
    """
    settings.MOLESON_ENCRYPTION_KEYS = [
        Fernet.generate_key().decode(),
        Fernet.generate_key().decode(),
    ]
    return settings.MOLESON_ENCRYPTION_KEYS


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.fixture
def staff_client(db, django_user_model) -> Client:
    """Client authentifié comme membre du secrétariat (accès administration)."""
    user = django_user_model.objects.create_user(
        username="secretariat-test",
        password="mot-de-passe-de-test",  # noqa: S106 - utilisateur jetable
        is_staff=True,
    )
    client = Client()
    client.force_login(user)
    return client
