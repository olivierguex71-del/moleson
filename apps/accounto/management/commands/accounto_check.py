"""Validation de la Phase 0 : Accounto peut-il porter la facturation de Moléson ?

Cette commande répond à une question précise, posée avant tout développement de
la Phase 2 : **l'API expose-t-elle le PDF d'une QR-facture conforme, et non
seulement une interface où la consulter ?** Une réponse négative ne coûte rien
aujourd'hui ; découverte après avoir bâti la facturation, elle coûterait la
refonte du module.

Quatre prérequis sont éprouvés dans l'ordre, chacun dépendant du précédent :

1. l'API répond et accepte nos identifiants ;
2. une facture peut être créée depuis Moléson ;
3. le PDF produit se récupère par l'API, et il est conforme ;
4. la corrélation et le suivi des paiements sont possibles — `external_identifier`
   n'étant pas inscriptible à la création, tout repose sur la `reference`, et
   l'absence de webhook impose d'interroger `updated_at_start`.

Aucune donnée personnelle réelle n'est envoyée : la facture d'essai porte des
coordonnées inventées.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounto.client import AccountoClient, AccountoError, AccountoNotConfigured
from apps.accounto.qrbill import verifier_pdf

#: Destinataire de la facture d'essai. Entièrement fictif : la Phase 0 pousse
#: des données vers un service tiers, jamais celles d'un participant réel.
DESTINATAIRE_FICTIF = {
    "name": "Destinataire de test Moléson",
    "street": "Rue de l'Exemple",
    "house_number": "1",
    "postal_code": "1700",
    "city": "Fribourg",
    "country": "CH",
    "email": "essai@example.invalid",
}

MONTANT_ESSAI = Decimal("42.55")


class Command(BaseCommand):
    help = "Éprouve les prérequis Accounto de la Phase 0 (staging)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-create",
            action="store_true",
            help="Ne créer aucune facture : n'éprouver que la lecture.",
        )
        parser.add_argument(
            "--invoice-id",
            help="Reprendre une facture existante au lieu d'en créer une.",
        )
        parser.add_argument(
            "--save-pdf",
            help="Enregistrer le PDF récupéré à ce chemin, pour examen à l'œil.",
        )

    def handle(self, *args, **options):
        self.echecs: list[str] = []
        client = AccountoClient()

        self._titre("Phase 0 — prérequis Accounto")
        # Chaque sortie anticipée passe par la conclusion : une commande qui
        # s'arrête sans verdict laisse croire qu'elle n'a rien trouvé à redire.
        if not self._etape_configuration(client):
            self._conclure()
            return
        if not self._etape_authentification(client):
            self._conclure()
            return

        facture = self._etape_creation(client, options)
        if facture is None:
            self._conclure()
            return

        pdf = self._etape_document(client, facture, options)
        if pdf is not None:
            self._etape_conformite(pdf)

        self._etape_suivi(client, facture)
        self._conclure()

    # --- Étapes ------------------------------------------------------------

    def _etape_configuration(self, client: AccountoClient) -> bool:
        self._titre("1. Configuration")
        if not client.is_configured:
            self._echec(
                "identifiants absents",
                "Renseigner ACCOUNTO_BASE_URL et ACCOUNTO_API_KEY dans .env, "
                "avec les accès de l'environnement de test.",
            )
            return False
        self._succes(f"URL de base configurée ({client.base_url})")
        self._succes("clé d'API présente")
        return True

    def _etape_authentification(self, client: AccountoClient) -> bool:
        self._titre("2. Accès à l'API")
        try:
            client.list_invoices(limit=1)
        except AccountoNotConfigured as exc:
            self._echec("identifiants absents", str(exc))
            return False
        except AccountoError as exc:
            detail = f"HTTP {exc.status} — {exc.body}" if exc.status else str(exc)
            self._echec("GET /invoices refusé", detail)
            return False
        self._succes("GET /invoices répond, les identifiants sont acceptés")
        return True

    def _etape_creation(self, client: AccountoClient, options: dict):
        self._titre("3. Création d'une facture")

        if options.get("invoice_id"):
            self._info(f"facture existante reprise : {options['invoice_id']}")
            try:
                return client.get_invoice(options["invoice_id"])
            except AccountoError as exc:
                self._echec("facture introuvable", str(exc))
                return None

        if options.get("no_create"):
            self._info("création ignorée (--no-create) : les étapes suivantes sont sautées")
            return None

        payload = {
            "recipient": DESTINATAIRE_FICTIF,
            "currency": "CHF",
            "date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=10)).isoformat(),
            "positions": [
                {
                    "description": "Essai de validation Moléson (Phase 0)",
                    "quantity": 1,
                    "unit_price": str(MONTANT_ESSAI),
                }
            ],
        }
        try:
            facture = client.create_invoice(payload)
        except AccountoError as exc:
            detail = f"HTTP {exc.status} — {exc.body}" if exc.status else str(exc)
            self._echec("POST /invoices refusé", detail)
            self._info(
                "La forme de la charge utile n'est pas figée : ce message d'erreur "
                "est précisément ce qui permet de l'ajuster."
            )
            return None

        identifiant = _premier(facture, "id", "invoice_id", "uuid")
        self._succes(f"facture créée{f' (id {identifiant})' if identifiant else ''}")

        reference = _premier(facture, "reference", "qr_reference", "payment_reference")
        if reference:
            self._succes(f"référence rendue à la création : {reference}")
        else:
            self._echec(
                "aucune référence rendue à la création",
                "La corrélation inscription ↔ facture repose sur elle, "
                "`external_identifier` n'étant pas inscriptible.",
            )
        return facture

    def _etape_document(self, client: AccountoClient, facture, options: dict):
        self._titre("4. Récupération du PDF")
        document_id = _premier(facture, "document_id", "pdf_id", "document", "id")
        if not document_id:
            self._echec(
                "identifiant de document absent",
                "La réponse de création ne désigne aucun document à télécharger.",
            )
            return None

        try:
            contenu, type_contenu = client.get_document(str(document_id))
        except AccountoError as exc:
            self._echec(f"GET /documents/{document_id} refusé", str(exc))
            return None

        self._succes(
            f"document récupéré ({len(contenu) // 1024} Ko, {type_contenu or 'type non annoncé'})"
        )
        if "pdf" not in type_contenu.lower():
            self._info(
                "Le type annoncé n'est pas un PDF : le contrôle de conformité "
                "dira si le contenu en est un malgré tout."
            )

        if chemin := options.get("save_pdf"):
            from pathlib import Path

            Path(chemin).write_bytes(contenu)
            self._info(f"PDF enregistré : {chemin}")
        return contenu

    def _etape_conformite(self, pdf: bytes) -> None:
        self._titre("5. Conformité de la QR-facture")
        rapport = verifier_pdf(pdf, montant_attendu=MONTANT_ESSAI)
        for constat in rapport.constats:
            if constat.conforme:
                self._succes(f"{constat.libelle}{f' — {constat.detail}' if constat.detail else ''}")
            else:
                self._echec(constat.libelle, constat.detail)

    def _etape_suivi(self, client: AccountoClient, facture) -> None:
        self._titre("6. Suivi des paiements")
        depuis = (date.today() - timedelta(days=1)).isoformat()
        try:
            resultat = client.list_invoices(updated_at_start=depuis, limit=50)
        except AccountoError as exc:
            self._echec("filtre updated_at_start refusé", str(exc))
            self._info("Sans lui, il faudrait relire toutes les factures à chaque passage.")
            return

        lignes = resultat if isinstance(resultat, list) else resultat.get("data", resultat)
        nombre = len(lignes) if isinstance(lignes, list) else "?"
        self._succes(f"GET /invoices?updated_at_start={depuis} répond ({nombre} facture(s))")

        reference = _premier(facture, "reference", "qr_reference", "payment_reference")
        if reference and isinstance(lignes, list):
            retrouvee = any(reference in str(ligne) for ligne in lignes)
            if retrouvee:
                self._succes("la facture d'essai se retrouve par sa référence")
            else:
                self._echec(
                    "facture d'essai non retrouvée par sa référence",
                    "La table de correspondance inscription ↔ facture ne pourrait "
                    "pas être tenue à jour.",
                )

    # --- Sortie ------------------------------------------------------------

    def _titre(self, texte: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{texte}"))

    def _succes(self, texte: str) -> None:
        self.stdout.write(f"  ✓ {texte}")

    def _info(self, texte: str) -> None:
        self.stdout.write(f"    {texte}")

    def _echec(self, titre: str, detail: str = "") -> None:
        self.stdout.write(self.style.ERROR(f"  ✗ {titre}"))
        if detail:
            self._info(detail)
        self.echecs.append(titre)

    def _conclure(self) -> None:
        self.stdout.write("")
        if self.echecs:
            self.stdout.write(
                self.style.ERROR(
                    f"Phase 0 non validée — {len(self.echecs)} prérequis non satisfait(s) :"
                )
            )
            for echec in self.echecs:
                self.stdout.write(self.style.ERROR(f"  · {echec}"))
            self.stdout.write("\nCes points sont à porter à Accounto avant d'engager la Phase 2.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Phase 0 validée : l'API rend une QR-facture conforme et permet "
                    "d'en suivre le paiement."
                )
            )


def _premier(donnees, *cles: str):
    """Première clé présente dans une réponse, à plat ou imbriquée.

    Les noms de champs de l'API ne sont pas connus avec certitude : on essaie
    les formes plausibles plutôt que d'échouer sur un nom deviné.
    """
    if not isinstance(donnees, dict):
        return None
    for cle in cles:
        if (valeur := donnees.get(cle)) not in (None, "", {}):
            return valeur
    for imbrique in ("data", "invoice", "result"):
        if isinstance(donnees.get(imbrique), dict):
            if trouve := _premier(donnees[imbrique], *cles):
                return trouve
    return None
