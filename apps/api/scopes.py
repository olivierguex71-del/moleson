"""Portées (scopes) de l'API Moléson.

L'API est le contrat vers l'extérieur : site public, portail formateurs, portail
participants. Chaque consommateur reçoit un jeu de portées, et une vue déclare
celles qu'elle exige. Ce découpage existe dès la Phase 1 — même quand
l'administration est le seul consommateur — parce que le rétro-ajouter à une API
déjà publiée coûte bien plus cher que de le poser tout de suite.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Scope(models.TextChoices):
    """Portées attribuables à un jeton ou à une session."""

    PUBLIC_READ = "public:read", _("Lecture publique (catalogue de cours)")
    ENROLMENT_WRITE = "enrolment:write", _("Créer une inscription depuis le site web")
    TRAINER_READ = "trainer:read", _("Portail formateurs — consultation")
    TRAINER_WRITE = "trainer:write", _("Portail formateurs — présences")
    PARTICIPANT_READ = "participant:read", _("Portail participant — consultation")
    PARTICIPANT_WRITE = "participant:write", _("Portail participant — reconduction, profil")
    ADMIN = "admin", _("Administration — accès complet")


#: Portées disponibles sans authentification.
ANONYMOUS_SCOPES: frozenset[str] = frozenset({Scope.PUBLIC_READ})


def scopes_for_user(user) -> frozenset[str]:
    """Portées effectives d'un utilisateur authentifié.

    Point d'extension : les rôles formateur et participant s'y brancheront quand
    les entités correspondantes existeront (session « schéma »). Aujourd'hui,
    seul le rôle d'administration est peuplé.
    """
    if not user or not user.is_authenticated:
        return ANONYMOUS_SCOPES
    if user.is_staff or user.is_superuser:
        return frozenset(Scope.values)
    return ANONYMOUS_SCOPES
