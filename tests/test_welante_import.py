"""Chaîne complète de migration, sur des classeurs reproduisant les anomalies réelles.

Ce que ces tests vérifient avant tout : la migration **ne laisse rien passer en
silence**. Une donnée écartée doit apparaître dans le rapport ; une donnée
importée doit être exacte.
"""

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.catalog.models import AdministrativeType, Course, Subject
from apps.communications.models import MailingCampaign, MailingDelivery
from apps.contacts.models import Contact, Membership, Trainer
from apps.enrolments.models import Enrolment
from tests.welante_fixtures import ecrire_tous_les_exports

pytestmark = pytest.mark.django_db


@pytest.fixture
def exports(tmp_path):
    """Cinq exports synthétiques, données entièrement inventées."""
    return ecrire_tous_les_exports(tmp_path / "data")


@pytest.fixture
def referentiels():
    call_command("seed_reference", verbosity=0)


TOUS = ["categories", "trainers", "members", "courses", "participants"]


def importer_avec_inscriptions(dossier) -> str:
    """Import complet, inscriptions comprises.

    Elles sont hors du parcours par défaut (voir PAR_DEFAUT) : les demander
    explicitement est le seul moyen de couvrir leur importeur, qui reste
    utilisable le jour où un export exploitable sera fourni.
    """
    return importer(dossier, only=TOUS)


def importer(dossier, **options) -> str:
    sortie = StringIO()
    call_command(
        "welante_import", source=str(dossier), commit=True, stdout=sortie, stderr=sortie, **options
    )
    return sortie.getvalue()


# --- Inspection ------------------------------------------------------------


def test_l_inspection_n_affiche_aucune_valeur_du_fichier(exports):
    """Contrôle nLPD : la sortie doit pouvoir être copiée dans un message."""
    sortie = StringIO()
    call_command("welante_inspect", source=str(exports), stdout=sortie)
    texte = sortie.getvalue()

    for valeur_personnelle in [
        "alex@example.invalid",
        "756.0000.0000.00",
        "CH9300762011623852957",
        "Nomdetest",
        "Fribourg",
    ]:
        assert valeur_personnelle not in texte

    assert "Intervenant-e-s" in texte
    assert "colonnes reconnues" in texte


def test_l_inspection_signale_les_colonnes_par_saison(exports):
    sortie = StringIO()
    call_command("welante_inspect", source=str(exports), stdout=sortie)

    assert "une par saison" in sortie.getvalue()


# --- Simulation ------------------------------------------------------------


def test_la_simulation_n_ecrit_rien(exports, referentiels):
    sortie = StringIO()
    call_command("welante_import", source=str(exports), stdout=sortie, stderr=sortie)

    assert "SIMULATION" in sortie.getvalue()
    assert Contact.objects.count() == 0
    assert Course.objects.count() == 0


def test_la_simulation_eprouve_les_vraies_contraintes(exports, referentiels):
    """Elle écrit puis annule : les contraintes de la base s'appliquent réellement."""
    simulation = StringIO()
    call_command("welante_import", source=str(exports), stdout=simulation, stderr=simulation)
    reel = importer(exports)

    for compteur in ["lignes lues", "importées"]:
        assert compteur in simulation.getvalue()
        assert compteur in reel


# --- Catégories ------------------------------------------------------------


def test_les_etiquettes_marketing_ne_deviennent_pas_des_matieres(exports, referentiels):
    importer(exports, only=["categories"])

    assert not Subject.objects.filter(name_fr__iexact="Newsletter").exists()
    assert not Subject.objects.filter(name_fr__iexact="ORS").exists()


def test_la_coquille_connue_est_corrigee(exports, referentiels):
    sortie = importer(exports, only=["categories"])

    assert Subject.objects.filter(name_fr__icontains="Technologie").exists()
    assert not Subject.objects.filter(name_fr__icontains="Technonolgie").exists()
    assert "coquille_corrigee" in sortie


def test_le_web_code_devient_le_slug(exports, referentiels):
    """Conserver l'identifiant public préserve les URL du site et leur référencement."""
    importer(exports, only=["categories"])

    assert Subject.objects.filter(slug="cours-de-langues").exists()


def test_la_hierarchie_a_deux_niveaux_est_reconstruite(exports, referentiels):
    importer(exports, only=["categories"])

    italien = Subject.objects.get(slug="italien")
    assert italien.parent is not None
    assert italien.parent.name_fr == "Cours de langues"


# --- Cours -----------------------------------------------------------------


def test_le_titre_concatene_est_decoupe_en_deux_langues(exports, referentiels):
    importer(exports, only=["categories", "courses"])

    cours = Course.objects.get(code="2026-T4-441001-FR")
    assert cours.title_de == "Englisch für Anfänger"
    assert cours.title_fr == "Anglais pour débutants"


def test_le_descriptif_bilingue_est_decoupe(exports, referentiels):
    importer(exports, only=["categories", "courses"])

    cours = Course.objects.get(code="2026-T4-441001-FR")
    assert cours.description_de.startswith("Dieser Kurs")
    assert cours.description_fr.startswith("Ce cours")


def test_la_region_vient_du_code_et_non_de_la_colonne_chiffre(exports, referentiels):
    """La colonne « Chiffre » vaut « R » pour FR, GL et GR : elle ne distingue rien."""
    importer(exports, only=["categories", "courses"])

    assert Course.objects.get(code="2026-T4-441001-FR").region.code == "FR"
    assert Course.objects.get(code="2026-T4-421002b-GR").region.code == "GR"
    assert Course.objects.get(code="2026-T4-441003-GL").region.code == "GL"


def test_la_periode_est_deduite_du_code_et_signalee_a_verifier(exports, referentiels):
    sortie = importer(exports, only=["categories", "courses"])

    cours = Course.objects.get(code="2026-T4-441001-FR")
    assert (cours.period.year, cours.period.kind) == (2026, "T4")
    assert "periode_creee" in sortie


def test_la_plage_de_participants_est_decoupee(exports, referentiels):
    importer(exports, only=["categories", "courses"])

    cours = Course.objects.get(code="2026-T4-441001-FR")
    assert (cours.min_participants, cours.max_participants) == (5, 8)


def test_le_prix_avec_apostrophe_de_milliers_est_lu(exports, referentiels):
    importer(exports, only=["categories", "courses"])

    assert Course.objects.get(code="2026-T4-421002b-GR").base_price == Decimal("1250.00")


def test_un_prix_illisible_est_signale_et_non_devine(exports, referentiels):
    sortie = importer(exports, only=["categories", "courses"])

    assert Course.objects.get(code="2026-T4-441003-GL").base_price == Decimal("0")
    assert "prix_illisible" in sortie


def test_un_code_herite_est_ecarte_pour_rattachement_manuel(exports, referentiels):
    sortie = importer(exports, only=["categories", "courses"])

    assert not Course.objects.filter(code="2021-72-1021-SN").exists()
    assert "code_herite" in sortie


def test_les_etiquettes_deviennent_des_flags_et_les_types_des_attributs(exports, referentiels):
    importer(exports, only=["categories", "courses"])

    assert Course.objects.get(code="2026-T4-441001-FR").in_newsletter is True
    assert (
        Course.objects.get(code="2026-T4-421002b-GR").administrative_type == AdministrativeType.ORS
    )


def test_les_statistiques_femme_et_age_ne_sont_pas_migrees(exports, referentiels):
    sortie = importer(exports, only=["categories", "courses"])

    assert "statistique_non_migree" in sortie
    assert not any(champ.name in ("women_share", "age") for champ in Course._meta.get_fields())


# --- Intervenants ----------------------------------------------------------


def test_les_iban_espaces_et_colles_convergent(exports, referentiels):
    importer(exports, only=["trainers"])

    ibans = set(Trainer.objects.exclude(iban="").values_list("iban", flat=True))
    assert ibans == {"CH9300762011623852957"}


def test_un_iban_a_cle_fausse_est_ecarte_et_signale(exports, referentiels):
    sortie = importer(exports, only=["trainers"])

    formateur = Trainer.objects.get(contact__last_name="Troistest")
    assert formateur.iban == ""
    assert "iban_iban_cle" in sortie


def test_un_bic_range_dans_la_colonne_banque_est_reconnu(exports, referentiels):
    sortie = importer(exports, only=["trainers"])

    formateur = Trainer.objects.get(contact__last_name="Zweitest")
    assert formateur.bic == "POFICHBEXXX"
    assert formateur.bank_name == ""
    assert "bic_dans_nom_de_banque" in sortie


def test_le_numero_avs_est_chiffre_a_l_import(exports, referentiels):
    from django.db import connection

    importer(exports, only=["trainers"])
    formateur = Trainer.objects.get(contact__last_name="Nomdetest")

    with connection.cursor() as cursor:
        cursor.execute("SELECT ahv_number FROM contacts_trainer WHERE id = %s", [formateur.pk])
        (stocke,) = cursor.fetchone()

    assert "756" not in stocke
    assert formateur.ahv_number == "756.0000.0000.00"


def test_une_coquille_de_localite_est_corrigee(exports, referentiels):
    importer(exports, only=["trainers"])

    assert Contact.objects.filter(city="Villars-sur-Glâne").exists()
    assert not Contact.objects.filter(city__contains=" -").exists()


def test_l_absence_de_courriel_est_signalee(exports, referentiels):
    sortie = importer(exports, only=["trainers"])

    assert "sans_courriel" in sortie


# --- Membres ---------------------------------------------------------------


def test_la_deuxieme_ligne_d_entete_est_sautee(exports, referentiels):
    """Sans cela, « Mitgliedschaft » deviendrait un contact."""
    importer(exports, only=["members"])

    assert not Contact.objects.filter(last_name__icontains="Mitglied").exists()
    assert Contact.objects.filter(last_name="Membretest").exists()


def test_les_colonnes_par_saison_deviennent_des_campagnes(exports, referentiels):
    """Anti-pattern corrigé : ajouter une saison ne modifiera plus le schéma."""
    sortie = importer(exports, only=["members"])

    assert MailingCampaign.objects.count() == 2
    assert MailingDelivery.objects.count() == 3
    assert "colonnes_par_saison" in sortie


def test_un_type_d_adhesion_connu_cree_une_adhesion(exports, referentiels):
    importer(exports, only=["members"])

    adhesion = Membership.objects.get(contact__last_name="Membretest")
    assert adhesion.type.code == "supporter"


def test_mitarbeiter_devient_un_role_et_non_une_adhesion(exports, referentiels):
    """C'est ce qui empêche le rabais collaborateur de se cumuler avec une adhésion."""
    sortie = importer(exports, only=["members"])

    contact = Contact.objects.get(last_name="Collabtest")
    assert contact.is_collaborator is True
    assert not contact.memberships.exists()
    assert "role_collaborateur" in sortie


def test_une_categorie_non_tranchee_est_signalee_sans_etre_devinee(exports, referentiels):
    sortie = importer(exports, only=["members"])

    contact = Contact.objects.get(last_name="Comitetest")
    assert not contact.memberships.exists()
    assert "categorie_a_arbitrer" in sortie


def test_le_journal_historique_part_en_archive(exports, referentiels):
    importer(exports, only=["members"])

    contact = Contact.objects.get(last_name="Membretest")
    assert "archive" in contact.legacy_notes


# --- Inscriptions ----------------------------------------------------------


def test_un_contact_inscrit_a_deux_cours_n_est_pas_dedouble(exports, referentiels):
    """28 contacts répétés dans l'export : ce sont des inscriptions, pas des doublons."""
    importer_avec_inscriptions(exports)

    assert Contact.objects.filter(email="camille@example.invalid").count() == 1
    assert Enrolment.objects.filter(participant__email="camille@example.invalid").count() == 2


def test_un_contact_de_facturation_distinct_est_cree(exports, referentiels):
    sortie = importer_avec_inscriptions(exports)

    inscription = Enrolment.objects.get(participant__last_name="Deuxiemetest")
    assert inscription.billing_contact is not None
    assert inscription.billing_contact.organisation == "Entreprise fictive SA"
    assert "payeur_a_completer" in sortie


def test_un_montant_qui_s_ecarte_du_tarif_devient_un_prix_impose(exports, referentiels):
    sortie = importer_avec_inscriptions(exports)

    inscription = Enrolment.objects.get(participant__last_name="Deuxiemetest")
    assert inscription.price_override == Decimal("285.00")
    assert inscription.price == Decimal("285.00")
    assert "prix_impose_repris" in sortie


def test_une_date_en_serie_excel_devient_une_vraie_date(exports, referentiels):
    importer_avec_inscriptions(exports)

    inscription = Enrolment.objects.filter(participant__last_name="Premiertest").first()
    assert inscription.enrolled_on.isoformat() == "2026-01-01"


def test_une_inscription_a_un_cours_inexistant_est_ecartee(exports, referentiels):
    sortie = importer_avec_inscriptions(exports)

    assert not Enrolment.objects.filter(participant__last_name="Quatriemetest").exists()
    assert "cours_introuvable" in sortie


def test_le_rapport_denombre_les_points_a_arbitrer(exports, referentiels):
    sortie = importer(exports)

    assert "arbitrage humain" in sortie


def test_le_rapport_csv_ne_contient_aucune_valeur_source(exports, referentiels, tmp_path):
    """Un rapport se garde en trace : il ne doit pas devenir un second exemplaire des données."""
    destination = tmp_path / "anomalies.csv"
    importer(exports, report=str(destination))

    contenu = "".join(
        fichier.read_text(encoding="utf-8") for fichier in tmp_path.glob("anomalies-*.csv")
    )
    assert contenu
    for valeur_personnelle in [
        "camille@example.invalid",
        "756.0000.0000.00",
        "CH9300762011623852957",
        "Premiertest",
    ]:
        assert valeur_personnelle not in contenu


def test_l_import_refuse_de_demarrer_sans_cle_de_chiffrement(exports, referentiels, settings):
    """Sans clé, l'écriture d'un no AVS échouerait au milieu du traitement.

    Refuser de démarrer vaut mieux que s'arrêter à la centième ligne, à moitié
    importé.
    """
    settings.MOLESON_ENCRYPTION_KEYS = []
    sortie = StringIO()

    call_command(
        "welante_import", source=str(exports), only=["trainers"], stdout=sortie, stderr=sortie
    )

    assert "MOLESON_ENCRYPTION_KEYS est vide" in sortie.getvalue()
    assert Trainer.objects.count() == 0


def test_les_autres_exports_restent_importables_sans_cle(exports, referentiels, settings):
    """Seuls les intervenants portent des données chiffrées."""
    settings.MOLESON_ENCRYPTION_KEYS = []
    sortie = StringIO()

    call_command(
        "welante_import",
        source=str(exports),
        only=["categories"],
        commit=True,
        stdout=sortie,
        stderr=sortie,
    )

    assert Subject.objects.exists()


def test_les_inscriptions_ne_sont_pas_reprises_par_defaut(exports, referentiels):
    """Décision de périmètre : l'export disponible ne contient que la file de
    reconduction, qui pointe vers des cours absents. L'importer produirait des
    centaines de rejets sans rien apporter.
    """
    importer(exports)

    assert Course.objects.exists()
    assert Contact.objects.exists()
    assert not Enrolment.objects.exists()


def test_les_inscriptions_restent_importables_sur_demande(exports, referentiels):
    """L'importeur n'est pas supprimé : il attend un export exploitable."""
    importer_avec_inscriptions(exports)

    assert Enrolment.objects.exists()
