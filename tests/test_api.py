"""L'API répond, publie son contrat et applique ses portées."""

import pytest
from django.test import RequestFactory

from apps.api.scopes import Scope
from apps.api.security import ScopedAuth

HEALTH = "/api/v1/health"
ME = "/api/v1/me"
OPENAPI = "/api/v1/openapi.json"


@pytest.mark.django_db
def test_le_healthcheck_voit_la_base(client):
    response = client.get(HEALTH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_le_contrat_openapi_est_publie(client):
    """C'est ce document que consommeront le site public et les portails."""
    response = client.get(OPENAPI)

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "API Moléson"
    assert HEALTH in schema["paths"]
    assert ME in schema["paths"]


@pytest.mark.django_db
def test_un_appelant_anonyme_n_a_que_la_lecture_publique(client):
    response = client.get(ME)

    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "scopes": [Scope.PUBLIC_READ.value]}


@pytest.mark.django_db
def test_le_secretariat_connecte_recoit_toutes_les_portees(staff_client):
    response = staff_client.get(ME)

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert Scope.ADMIN.value in body["scopes"]


@pytest.mark.django_db
def test_un_jeton_porteur_inconnu_est_refuse(client):
    """Un jeton présenté et refusé est une erreur — pas un repli vers l'anonyme."""
    response = client.get(ME, headers={"Authorization": "Bearer jeton-inexistant"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_une_ecriture_par_session_ne_confere_aucune_portee(django_user_model):
    """Garde-fou CSRF : les écritures devront passer par un jeton porteur.

    Un cookie de session accompagne automatiquement une requête déclenchée depuis
    un autre site ; un jeton porteur, non.
    """
    utilisateur = django_user_model.objects.create_user(username="secretariat", is_staff=True)
    auth = ScopedAuth()

    lecture = RequestFactory().get(ME)
    lecture.user = utilisateur
    ecriture = RequestFactory().post(ME)
    ecriture.user = utilisateur

    assert Scope.ADMIN.value in auth.resolve_session(lecture).scopes
    assert auth.resolve_session(ecriture).scopes == frozenset({Scope.PUBLIC_READ})
