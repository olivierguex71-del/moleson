"""Client de l'API Accounto.

Volontairement mince : Moléson pousse une facture, récupère le PDF que le
service a produit, puis interroge périodiquement l'état des paiements. Il n'y a
ni webhook à recevoir ni comptabilité à tenir de notre côté — Accounto est
l'ERP, Moléson affiche.

**La forme exacte des charges utiles n'est pas figée ici.** La documentation de
l'API n'ayant pas été confrontée à un environnement réel, le client transmet ce
qu'on lui donne et rend ce qu'il reçoit ; c'est la commande `accounto_check` qui
sert à établir la forme juste, avant que la Phase 2 ne s'appuie dessus.
"""

from dataclasses import dataclass, field
from typing import Any

import httpx
from django.conf import settings

#: Au-delà, l'API est considérée comme indisponible plutôt que lente.
DELAI_PAR_DEFAUT = 30.0


class AccountoError(RuntimeError):
    """Échec d'un appel à l'API, avec de quoi le diagnostiquer."""

    def __init__(self, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        # Tronqué : un corps d'erreur peut contenir l'écho de ce qu'on a envoyé.
        self.body = body[:500]


class AccountoNotConfigured(AccountoError):
    """L'URL ou la clé d'API manquent."""


@dataclass
class AccountoClient:
    """Accès HTTP à Accounto.

    Les identifiants viennent de la configuration ; ils ne sont jamais écrits
    dans un journal ni dans un message d'erreur.
    """

    base_url: str = ""
    api_key: str = ""
    timeout: float = DELAI_PAR_DEFAUT
    #: Transport HTTP de remplacement, pour éprouver le client sans réseau.
    transport: httpx.BaseTransport | None = None
    _appels: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.base_url = (self.base_url or settings.ACCOUNTO_BASE_URL or "").rstrip("/")
        self.api_key = self.api_key or settings.ACCOUNTO_API_KEY or ""

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _require_configuration(self) -> None:
        if not self.is_configured:
            raise AccountoNotConfigured(
                "ACCOUNTO_BASE_URL et ACCOUNTO_API_KEY doivent être renseignés dans .env."
            )

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Envoie une requête et rend la réponse brute, sans l'interpréter."""
        self._require_configuration()
        url = f"{self.base_url}/{path.lstrip('/')}"
        entetes = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            **kwargs.pop("headers", {}),
        }
        self._appels.append(f"{method} {path}")
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, transport=self.transport
            ) as client:
                return client.request(method, url, headers=entetes, **kwargs)
        except httpx.HTTPError as exc:
            raise AccountoError(f"Appel {method} {path} impossible : {exc}") from exc

    def get_json(self, path: str, **params) -> Any:
        reponse = self.request("GET", path, params=params or None)
        self._verifier(reponse, path)
        try:
            return reponse.json()
        except ValueError as exc:
            raise AccountoError(
                f"{path} n'a pas répondu du JSON.", status=reponse.status_code, body=reponse.text
            ) from exc

    def post_json(self, path: str, payload: dict) -> Any:
        reponse = self.request(
            "POST", path, json=payload, headers={"Content-Type": "application/json"}
        )
        self._verifier(reponse, path)
        try:
            return reponse.json()
        except ValueError:
            return {}

    def get_bytes(self, path: str, *, accept: str = "application/pdf") -> tuple[bytes, str]:
        """Récupère un contenu binaire — le PDF de la QR-facture.

        Rend aussi le type de contenu annoncé : c'est lui qui dit si l'API
        expose réellement un PDF, ou seulement une page à afficher.
        """
        reponse = self.request("GET", path, headers={"Accept": accept})
        self._verifier(reponse, path)
        return reponse.content, reponse.headers.get("Content-Type", "")

    @staticmethod
    def _verifier(reponse: httpx.Response, path: str) -> None:
        if reponse.is_success:
            return
        raise AccountoError(
            f"{path} a répondu {reponse.status_code}.",
            status=reponse.status_code,
            body=reponse.text,
        )

    # --- Opérations métier -------------------------------------------------

    def list_invoices(self, *, updated_at_start: str | None = None, limit: int = 10) -> Any:
        """Factures modifiées depuis une date — le mécanisme de suivi des paiements.

        Accounto n'émet pas de webhook : c'est cette requête, appelée
        périodiquement, qui apprend à Moléson qu'une facture a été payée.
        """
        params: dict[str, Any] = {"limit": limit}
        if updated_at_start:
            params["updated_at_start"] = updated_at_start
        return self.get_json("/invoices", **params)

    def create_invoice(self, payload: dict) -> Any:
        return self.post_json("/invoices", payload)

    def get_invoice(self, invoice_id: str) -> Any:
        return self.get_json(f"/invoices/{invoice_id}")

    def get_document(self, document_id: str) -> tuple[bytes, str]:
        """Récupère un document produit par Accounto, PDF de QR-facture compris."""
        return self.get_bytes(f"/documents/{document_id}")
