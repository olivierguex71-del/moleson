"""Authentification et contrôle des portées de l'API.

Deux mécanismes cohabiteront :

- **Jetons porteurs** — le mode normal pour les consommateurs externes (site
  public, portails). Le modèle `ApiToken` arrive avec le schéma ; le point
  d'accroche est `ScopedAuth.resolve_bearer`.
- **Session Django** — commodité de développement : une fois connecté à
  l'administration, on explore l'API depuis le navigateur. Restreint aux méthodes
  sûres, faute de quoi ce serait une porte ouverte au CSRF.

L'authentification réussit toujours et produit un `Caller`, éventuellement
anonyme. C'est la vue qui tranche, via `require_scopes` : une même route peut
ainsi servir des données publiques et en révéler davantage à un appelant
identifié, sans dupliquer l'endpoint.
"""

from dataclasses import dataclass, field

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security.base import AuthBase

from apps.api.scopes import ANONYMOUS_SCOPES, scopes_for_user

#: Méthodes HTTP sans effet de bord, seules autorisées via la session Django.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class Caller:
    """L'appelant d'une requête API, tel que résolu par `ScopedAuth`.

    Accessible dans une vue via `request.auth`.
    """

    scopes: frozenset[str]
    user: object = field(default_factory=AnonymousUser)

    @property
    def is_authenticated(self) -> bool:
        return bool(getattr(self.user, "is_authenticated", False))

    def has(self, *scopes: str) -> bool:
        return set(scopes) <= self.scopes


class ScopedAuth(AuthBase):
    """Résout les portées de l'appelant et les expose sur `request.auth`."""

    openapi_type = "http"
    openapi_scheme = "bearer"

    def __call__(self, request: HttpRequest) -> Caller:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and token:
            if caller := self.resolve_bearer(request, token.strip()):
                return caller
            raise HttpError(401, "Jeton invalide ou révoqué.")
        return self.resolve_session(request)

    def resolve_bearer(self, request: HttpRequest, token: str) -> Caller | None:  # pragma: no cover
        """Résolution d'un jeton porteur.

        Sera implémentée avec le modèle `ApiToken` (session « schéma ») :
        recherche par empreinte, vérification de l'expiration et de la révocation.
        Renvoyer `None` sur un jeton inconnu — un jeton présenté et refusé est une
        erreur explicite, pas un repli silencieux vers l'accès anonyme.
        """
        return None

    def resolve_session(self, request: HttpRequest) -> Caller:
        user = getattr(request, "user", None)
        if user and user.is_authenticated and request.method in SAFE_METHODS:
            return Caller(scopes=scopes_for_user(user), user=user)
        # Une écriture authentifiée par cookie de session serait vulnérable au
        # CSRF : on la traite en anonyme. Les écritures passent par un jeton.
        return Caller(scopes=ANONYMOUS_SCOPES)


#: Instance unique montée sur l'API.
scoped_auth = ScopedAuth()


def require_scopes(request: HttpRequest, *required: str) -> Caller:
    """Vérifie que l'appelant porte toutes les portées demandées, sinon lève 403.

    À appeler en début de vue :

        @api.get("/cours")
        def liste_cours(request):
            require_scopes(request, Scope.PUBLIC_READ)
    """
    caller: Caller = getattr(request, "auth", None) or Caller(scopes=ANONYMOUS_SCOPES)
    if missing := set(required) - set(caller.scopes):
        raise HttpError(403, f"Portées manquantes : {', '.join(sorted(missing))}")
    return caller
