"""Classeurs Excel synthétiques reproduisant les anomalies des exports Welante.

Les vrais exports ne peuvent pas servir de fixtures : ils contiennent des
numéros AVS, des IBAN et des adresses (nLPD), et ils ne circulent pas entre
machines. Ces classeurs rejouent donc **les anomalies décrites dans
`docs/analyse-exports-welante.md`** avec des données entièrement inventées :

- titres et descriptifs allemand + français concaténés ;
- catégories multiples avec hiérarchie « Parent > Enfant » et étiquettes mêlées ;
- colonne « Chiffre », « Femme », « Âge » — artefacts et statistiques ;
- « TN Min-Max » en texte ;
- IBAN tantôt espacés, tantôt collés, tantôt faux, tantôt absents ;
- dates en numéro de série Excel ;
- deuxième ligne d'en-tête dans le fichier des membres ;
- une colonne par saison d'envoi.
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook as OpenpyxlWorkbook

#: IBAN à clé valide, sur des numéros de compte inventés.
IBAN_VALIDE = "CH9300762011623852957"
IBAN_FAUX = "CH9300762011623852958"


def ecrire_categories(dossier: Path) -> Path:
    chemin = dossier / "Cate_gories_vhsfr_2026.xlsx"
    pd.DataFrame(
        [
            {"Catégorie": "Cours de langues", "Web-Code": "cours-de-langues", "Ordre": "1"},
            {
                "Catégorie": "Cours de langues > Italienisch / Italien",
                "Web-Code": "italien",
                "Ordre": "2",
            },
            # Coquille présente dans les données sources.
            {
                "Catégorie": "Informatique & Technonolgie",
                "Web-Code": "informatique",
                "Ordre": "3",
            },
            # Étiquette marketing mêlée aux matières.
            {"Catégorie": "Newsletter", "Web-Code": "newsletter", "Ordre": "4"},
            # Type administratif mêlé aux matières.
            {"Catégorie": "ORS", "Web-Code": "ors", "Ordre": "5"},
        ]
    ).to_excel(chemin, index=False)
    return chemin


def ecrire_cours(dossier: Path) -> Path:
    chemin = dossier / "Cours_Tous-2026.xlsx"
    pd.DataFrame(
        [
            {
                "Code": "2026-T4-441001-FR",
                "Titre": "Englisch für Anfänger / Anglais pour débutants",
                "Descriptif": (
                    "Dieser Kurs richtet sich an alle, die mit uns die Grundlagen lernen "
                    "möchten.\nCe cours s'adresse à toutes les personnes qui souhaitent "
                    "apprendre les bases."
                ),
                "Catégories": "Cours de langues > Italien; Newsletter",
                "Prix": "300.00",
                "TN Min-Max": "5 - 8",
                "Chiffre": "R",
                "Femme": "100%",
                "Âge": "45",
            },
            {
                "Code": "2026-T4-421002b-GR",
                "Titre": "Kochkurs für alle / Cours de cuisine pour tous",
                "Descriptif": "",
                "Catégories": "ORS",
                "Prix": "1'250.00",
                "TN Min-Max": "6",
                "Chiffre": "R",
                "Femme": "0%",
                "Âge": "",
            },
            # Code au format antérieur à 2023 : ni période ni région déductibles.
            {
                "Code": "2021-72-1021-SN",
                "Titre": "Aquagym",
                "Descriptif": "",
                "Catégories": "",
                "Prix": "200",
                "TN Min-Max": "",
                "Chiffre": "N",
                "Femme": "",
                "Âge": "",
            },
            # Prix illisible.
            {
                "Code": "2026-T4-441003-GL",
                "Titre": "Yoga",
                "Descriptif": "",
                "Catégories": "",
                "Prix": "sur demande",
                "TN Min-Max": "",
                "Chiffre": "L",
                "Femme": "",
                "Âge": "",
            },
        ]
    ).to_excel(chemin, index=False)
    return chemin


def ecrire_intervenants(dossier: Path) -> Path:
    chemin = dossier / "Intervenant-e-s-2026.xlsx"
    pd.DataFrame(
        [
            {
                "Nom": "Nomdetest",
                "Prénom": "Alex",
                "Email": "alex@example.invalid",
                "NPA": "1700",
                "Localité": "Fribourg",
                "Langue": "fr",
                "IBAN": "CH93 0076 2011 6238 5295 7",  # espacé
                "Bank IBANname": "Banque fictive",
                "No AVS": "756.0000.0000.00",
                "Renonciation AVS": "non",
            },
            {
                "Nom": "Zweitest",
                "Prénom": "Kim",
                "Email": "kim@example.invalid",
                "NPA": "3186",
                "Localité": "Düdingen",
                "Langue": "de",
                "IBAN": IBAN_VALIDE,  # collé
                "Bank IBANname": "POFICHBEXXX",  # un BIC dans la colonne du nom
                "No AVS": "",
                "Renonciation AVS": "ja",
            },
            {
                "Nom": "Troistest",
                "Prénom": "Dominique",
                "Email": "dominique@example.invalid",
                "NPA": "1630",
                "Localité": "Bulle",
                "Langue": "fr",
                "IBAN": IBAN_FAUX,  # clé de contrôle fausse
                "Bank IBANname": "",
                "No AVS": "",
                "Renonciation AVS": "",
            },
            {
                "Nom": "Quatretest",
                "Prénom": "Claude",
                "Email": "",  # sans courriel
                "NPA": "1700",
                "Localité": "Villars -sur-Glâne",  # coquille d'espacement
                "Langue": "",
                "IBAN": "",  # absent
                "Bank IBANname": "",
                "No AVS": "",
                "Renonciation AVS": "",
            },
        ]
    ).to_excel(chemin, index=False)
    return chemin


def ecrire_participants(dossier: Path) -> Path:
    chemin = dossier / "Participant-e-s_2026.xlsx"
    pd.DataFrame(
        [
            {
                "Nom": "Premiertest",
                "Prénom": "Camille",
                "Email": "camille@example.invalid",
                "NPA": "1700",
                "Localité": "Fribourg",
                "Langue": "fr",
                "Cours": "2026-T4-441001-FR",
                "Statut": "Copié",
                "Facturation": "",
                "Créé": "46023",  # série Excel
                "Prix": "",
            },
            # Même personne, autre cours : ce n'est pas un doublon.
            {
                "Nom": "Premiertest",
                "Prénom": "Camille",
                "Email": "camille@example.invalid",
                "NPA": "1700",
                "Localité": "Fribourg",
                "Langue": "fr",
                "Cours": "2026-T4-421002b-GR",
                "Statut": "Copié",
                "Facturation": "",
                "Créé": "46023",
                "Prix": "",
            },
            # Contact de facturation distinct.
            {
                "Nom": "Deuxiemetest",
                "Prénom": "Dominique",
                "Email": "dominique.d@example.invalid",
                "NPA": "1630",
                "Localité": "Bulle",
                "Langue": "fr",
                "Cours": "2026-T4-441001-FR",
                "Statut": "Copié",
                "Facturation": "Entreprise fictive SA",
                "Créé": "46023",
                "Prix": "285.00",  # montant qui s'écarte du tarif
            },
            # Sans courriel : magic link impossible.
            {
                "Nom": "Troisiemetest",
                "Prénom": "Sacha",
                "Email": "",
                "NPA": "3186",
                "Localité": "Düdingen",
                "Langue": "de",
                "Cours": "2026-T4-441001-FR",
                "Statut": "Copié",
                "Facturation": "",
                "Créé": "",
                "Prix": "",
            },
            # Cours inexistant.
            {
                "Nom": "Quatriemetest",
                "Prénom": "Noa",
                "Email": "noa@example.invalid",
                "NPA": "1700",
                "Localité": "Fribourg",
                "Langue": "fr",
                "Cours": "2026-T4-999999-FR",
                "Statut": "Copié",
                "Facturation": "",
                "Créé": "",
                "Prix": "",
            },
        ]
    ).to_excel(chemin, index=False)
    return chemin


def ecrire_membres(dossier: Path) -> Path:
    """Écrit `membres.xlsx` avec sa deuxième ligne d'en-tête partielle."""
    chemin = dossier / "membres.xlsx"
    classeur = OpenpyxlWorkbook()
    feuille = classeur.active

    entetes = [
        "Nom",
        "Prénom",
        "Email",
        "NPA",
        "Localité",
        "Langue",
        "Mitglieder",
        "Depuis",
        "Notes",
        "Programmversand Herbst 2019",
        "Programmversand Frühling 2020",
    ]
    feuille.append(entetes)
    # Deuxième ligne d'en-tête partielle, à sauter.
    feuille.append(["", "", "", "", "", "", "Mitgliedschaft", "", "", "", ""])

    feuille.append(
        [
            "Membretest",
            "Alex",
            "alex.m@example.invalid",
            "1700",
            "Fribourg",
            "fr",
            "Supporter-Mitglied",
            "01.01.2020",
            "Note historique reprise en archive.",
            "x",
            "x",
        ]
    )
    feuille.append(
        [
            "Comitetest",
            "Kim",
            "kim.m@example.invalid",
            "3186",
            "Düdingen",
            "de",
            "Vorstandsmitglied",  # correspondance non tranchée
            "",
            "",
            "",
            "x",
        ]
    )
    feuille.append(
        [
            "Collabtest",
            "Dominique",
            "dominique.m@example.invalid",
            "1630",
            "Bulle",
            "fr",
            "Mitarbeiter",  # un rôle, pas une adhésion
            "01.01.2021",
            "",
            "",
            "",
        ]
    )

    classeur.save(chemin)
    return chemin


def ecrire_tous_les_exports(dossier: Path) -> Path:
    """Écrit les cinq exports synthétiques dans un dossier."""
    dossier.mkdir(parents=True, exist_ok=True)
    ecrire_categories(dossier)
    ecrire_cours(dossier)
    ecrire_intervenants(dossier)
    ecrire_participants(dossier)
    ecrire_membres(dossier)
    return dossier
