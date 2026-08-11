"""Phase 0 : Accounto peut-il porter la facturation de Moléson ?

Les identifiants de l'environnement de test n'étant pas encore disponibles, ces
tests éprouvent tout ce qui ne dépend pas d'eux : le client face à des réponses
simulées, et surtout **le contrôle de conformité**, sur de vrais PDF fabriqués
pour l'occasion.

Un contrôle de conformité que l'on n'a pas éprouvé sur un document non conforme
ne prouve rien : chaque vérification a donc sa contre-épreuve.
"""

from decimal import Decimal
from io import StringIO

import httpx
import pytest
from django.core.management import call_command

from apps.accounto.client import AccountoClient, AccountoError, AccountoNotConfigured
from apps.accounto.qrbill import verifier_pdf

# Coordonnées de paiement de l'institution, relevées dans l'analyse des exports.
# Elles figurent sur toute facture émise : ce ne sont pas des données personnelles.
QR_IBAN = "CH21 3000 0001 1700 4851 9"
REFERENCE = "00 00000 00016 65740 00018 40088"
IBAN_ORDINAIRE = "CH93 0076 2011 6238 5295 7"


def bulletin_pdf(
    *,
    iban: str = QR_IBAN,
    reference: str = REFERENCE,
    montant: str = "42.55",
    recepisse: bool = True,
    section: bool = True,
    devise: str = "CHF",
) -> bytes:
    """Fabrique un PDF imitant un bulletin de versement.

    Volontairement paramétrable : c'est en retirant une mention ou en faussant
    une valeur que l'on vérifie que le contrôle refuse ce qu'il doit refuser.
    """
    from weasyprint import HTML

    morceaux = ["<h1>Université populaire du canton de Fribourg</h1>"]
    if recepisse:
        morceaux.append("<h2>Récépissé</h2>")
    if section:
        morceaux.append("<h2>Section paiement</h2>")
    morceaux.append(f"<p>Compte / Payable à<br>{iban}</p>")
    morceaux.append(f"<p>Référence<br>{reference}</p>")
    morceaux.append(f"<p>Monnaie {devise} Montant {montant}</p>")
    return HTML(string="".join(morceaux)).write_pdf()


# --- Contrôle de conformité ------------------------------------------------


def test_un_bulletin_conforme_est_accepte():
    rapport = verifier_pdf(bulletin_pdf(), montant_attendu=Decimal("42.55"))

    assert rapport.conforme, [str(echec) for echec in rapport.echecs]
    assert rapport.reference.endswith("40088")


def test_un_contenu_qui_n_est_pas_un_pdf_est_refuse():
    """Cas réel à craindre : l'API rend une page HTML ou un message d'erreur."""
    rapport = verifier_pdf(b"<html><body>Veuillez vous connecter</body></html>")

    assert not rapport.conforme
    assert "PDF" in rapport.echecs[0].libelle


def test_une_reference_a_cle_fausse_est_refusee():
    """Le contrôle qui distingue un document plausible d'un document payable."""
    faussee = REFERENCE[:-1] + ("7" if REFERENCE[-1] != "7" else "6")

    rapport = verifier_pdf(bulletin_pdf(reference=faussee))

    assert not rapport.conforme
    assert any("contrôle de clé" in echec.libelle for echec in rapport.echecs)


def test_une_reference_structuree_avec_un_iban_ordinaire_est_signalee():
    """Une référence QRR exige un QR-IBAN : la banque rejetterait le bulletin."""
    rapport = verifier_pdf(bulletin_pdf(iban=IBAN_ORDINAIRE))

    assert not rapport.conforme
    assert any("QR-IBAN s'accorde" in echec.libelle for echec in rapport.echecs)


@pytest.mark.parametrize("manquante", ["recepisse", "section"])
def test_une_mention_normalisee_manquante_est_detectee(manquante):
    rapport = verifier_pdf(bulletin_pdf(**{manquante: False}))

    assert not rapport.conforme


def test_une_devise_etrangere_est_detectee():
    """Tout est en francs : un bulletin en euros signale une erreur de configuration."""
    rapport = verifier_pdf(bulletin_pdf(devise="EUR"))

    assert not rapport.conforme
    assert any("CHF" in echec.libelle for echec in rapport.echecs)


def test_un_montant_different_de_celui_demande_est_signale():
    rapport = verifier_pdf(bulletin_pdf(montant="99.00"), montant_attendu=Decimal("42.55"))

    assert not rapport.conforme
    assert any("montant facturé" in echec.libelle for echec in rapport.echecs)


def test_le_montant_n_est_pas_controle_si_on_n_en_attend_aucun():
    rapport = verifier_pdf(bulletin_pdf(montant="99.00"))

    assert rapport.conforme


# --- Client ----------------------------------------------------------------


def client_simule(reponses: dict, **kwargs) -> AccountoClient:
    """Client branché sur des réponses fixées, sans réseau."""

    def repondre(requete: httpx.Request) -> httpx.Response:
        for chemin, reponse in reponses.items():
            if requete.url.path.endswith(chemin):
                return reponse
        return httpx.Response(404, text="chemin non simulé")

    return AccountoClient(
        base_url="https://accounto.test/api",
        api_key="cle-de-test",
        transport=httpx.MockTransport(repondre),
        **kwargs,
    )


def test_le_client_lit_la_liste_des_factures():
    client = client_simule({"/invoices": httpx.Response(200, json=[{"id": "abc"}])})

    assert client.list_invoices() == [{"id": "abc"}]


def test_le_client_transmet_le_filtre_de_suivi():
    """Sans webhook, c'est updated_at_start qui apprend qu'une facture est payée."""
    vues: list[str] = []

    def repondre(requete):
        vues.append(str(requete.url))
        return httpx.Response(200, json=[])

    client = AccountoClient(
        base_url="https://accounto.test/api",
        api_key="cle",
        transport=httpx.MockTransport(repondre),
    )
    client.list_invoices(updated_at_start="2026-08-01")

    assert "updated_at_start=2026-08-01" in vues[0]


def test_le_client_rend_le_type_de_contenu_du_document():
    """C'est lui qui dit si l'API expose un PDF ou seulement une page à afficher."""
    client = client_simule(
        {
            "/documents/42": httpx.Response(
                200, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"}
            )
        }
    )

    contenu, type_contenu = client.get_document("42")

    assert contenu.startswith(b"%PDF")
    assert type_contenu == "application/pdf"


def test_une_erreur_de_l_api_est_remontee_avec_son_code():
    client = client_simule({"/invoices": httpx.Response(401, text="jeton expiré")})

    with pytest.raises(AccountoError) as erreur:
        client.list_invoices()

    assert erreur.value.status == 401
    assert "jeton expiré" in erreur.value.body


def test_le_corps_d_erreur_est_tronque():
    """Un corps d'erreur peut renvoyer l'écho de ce qu'on a transmis."""
    client = client_simule({"/invoices": httpx.Response(400, text="x" * 5000)})

    with pytest.raises(AccountoError) as erreur:
        client.list_invoices()

    assert len(erreur.value.body) <= 500


def test_un_client_sans_identifiants_le_dit_clairement(settings):
    settings.ACCOUNTO_BASE_URL = ""
    settings.ACCOUNTO_API_KEY = ""

    client = AccountoClient()

    assert not client.is_configured
    with pytest.raises(AccountoNotConfigured, match="ACCOUNTO_BASE_URL"):
        client.list_invoices()


# --- Commande de validation ------------------------------------------------


def test_la_commande_s_arrete_proprement_sans_identifiants(settings):
    """Sans accès à l'environnement de test, la commande doit dire quoi faire."""
    settings.ACCOUNTO_BASE_URL = ""
    settings.ACCOUNTO_API_KEY = ""
    sortie = StringIO()

    call_command("accounto_check", stdout=sortie, stderr=sortie)
    texte = sortie.getvalue()

    assert "identifiants absents" in texte
    assert "ACCOUNTO_BASE_URL" in texte
    assert "Phase 0 non validée" in texte


def test_la_commande_n_envoie_aucune_donnee_personnelle():
    """La Phase 0 pousse des données vers un tiers : elles doivent être inventées."""
    from apps.accounto.management.commands.accounto_check import DESTINATAIRE_FICTIF

    assert DESTINATAIRE_FICTIF["email"].endswith(".invalid")
    assert "test" in DESTINATAIRE_FICTIF["name"].lower()
