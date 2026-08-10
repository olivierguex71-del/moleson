"""Racine de l'API Moléson.

Le contrat public du projet. Les routeurs des entités métier viendront s'y
enregistrer (`api.add_router("/cours", cours_router)`) au fil de la Phase 1.

Le schéma OpenAPI est servi sur `/api/v1/openapi.json`, la documentation
interactive sur `/api/v1/docs` : c'est ce document que consommeront le site
public et les portails.
"""

from django.db import connection
from ninja import NinjaAPI, Schema

from apps.api.security import require_scopes, scoped_auth

api = NinjaAPI(
    title="API Moléson",
    version="1.0.0",
    description=(
        "API de la plateforme de cours de l'Université populaire du canton de Fribourg. "
        "Les contenus sont bilingues : chaque champ traduit existe en `_fr` et en `_de`."
    ),
    auth=scoped_auth,
    urls_namespace="moleson-api",
)


class HealthOut(Schema):
    status: str
    database: str


class CallerOut(Schema):
    authenticated: bool
    scopes: list[str]


@api.get("/health", response=HealthOut, auth=None, tags=["service"])
def health(request) -> HealthOut:
    """Vérifie que l'application répond et que la base est joignable.

    Utilisé par le healthcheck du conteneur : il doit rester sans authentification
    et sans effet de bord.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database = "ok"
    except Exception:
        # Le healthcheck rapporte l'état, il ne propage pas : une base injoignable
        # doit produire un « degraded » lisible, pas une 500 opaque.
        database = "unreachable"
    return HealthOut(status="ok" if database == "ok" else "degraded", database=database)


@api.get("/me", response=CallerOut, tags=["service"])
def me(request) -> CallerOut:
    """Portées effectives de l'appelant — sert à diagnostiquer un problème d'accès."""
    caller = require_scopes(request)
    return CallerOut(
        authenticated=caller.is_authenticated,
        scopes=sorted(caller.scopes),
    )
