"""Description des cinq exports Welante.

Les intitulés exacts des colonnes ne sont pas connus d'avance : les exports ont
été produits par une interface bilingue, et l'analyse ne cite qu'une partie des
en-têtes. Chaque colonne est donc décrite avec plusieurs intitulés possibles,
français et allemands.

Une colonne introuvable ne fait pas échouer l'import : `welante_inspect` la
signale, et l'ajustement se fait ici, en une passe, plutôt qu'en découvrant les
écarts un par un à l'exécution.
"""

from dataclasses import dataclass, field

from apps.welante.columns import Column


@dataclass(frozen=True)
class Source:
    """Un export : comment le trouver, comment le lire, ce qu'on y attend."""

    key: str
    label: str
    pattern: str
    columns: list[Column]
    header_row: int = 0
    skip_rows: tuple[int, ...] = ()
    note: str = ""

    @property
    def required_columns(self) -> list[Column]:
        return [colonne for colonne in self.columns if colonne.required]


CATEGORIES = Source(
    key="categories",
    label="Catégories",
    pattern="Cate_gories_vhsfr_*.xlsx",
    note="Taxonomie à deux niveaux ; le Web-Code devient le slug, à préserver.",
    columns=[
        Column("name", ("Catégorie", "Kategorie", "Nom", "Name", "Bezeichnung"), required=True),
        Column("web_code", ("Web-Code", "Webcode", "Web Code", "Code web")),
        Column("parent", ("Parent", "Übergeordnet", "Catégorie parente", "Oberkategorie")),
        Column("position", ("Ordre", "Position", "Reihenfolge", "Sortierung")),
    ],
)

COURSES = Source(
    key="courses",
    label="Cours",
    pattern="Cours_Tous-*.xlsx",
    note="Titre et descriptif contiennent l'allemand et le français concaténés.",
    columns=[
        Column("code", ("Code", "Numéro", "Nummer", "Kursnummer", "N°"), required=True),
        Column("title", ("Titre", "Titel", "Nom", "Bezeichnung"), required=True),
        Column("description", ("Descriptif", "Description", "Beschreibung", "Inhalt")),
        Column("categories", ("Catégories", "Kategorien", "Catégorie", "Kategorie")),
        Column("price", ("Prix", "Preis", "Tarif", "Kosten")),
        Column("participants", ("TN Min-Max", "TN Min Max", "Participants", "Teilnehmer")),
        Column("location", ("Lieu", "Ort", "Standort")),
        Column("trainer", ("Intervenant", "Intervenant-e", "Referent", "Kursleiter")),
        Column("period", ("Période", "Periode", "Semestre", "Trimestre")),
        Column(
            "digit",
            ("Chiffre", "Ziffer"),
            note="Artefact d'export : dernière lettre du suffixe régional, à ignorer.",
        ),
        Column("women_share", ("Femme", "Frauen"), note="Statistique dérivée, non migrée."),
        Column("age", ("Âge", "Alter"), note="Statistique dérivée, non migrée."),
    ],
)

TRAINERS = Source(
    key="trainers",
    label="Intervenant-e-s",
    pattern="Intervenant-e-s-*.xlsx",
    note="Contient des numéros AVS : données sensibles, chiffrées à l'import.",
    columns=[
        Column("last_name", ("Nom", "Name", "Nachname"), required=True),
        Column("first_name", ("Prénom", "Vorname")),
        Column("email", ("Email", "E-Mail", "Courriel", "Mail")),
        Column("phone", ("Téléphone", "Telefon", "Tél.", "Tel")),
        Column("mobile", ("Mobile", "Natel", "Handy", "Portable")),
        Column("street", ("Rue", "Strasse", "Adresse", "Adresse 1")),
        Column("postal_code", ("NPA", "PLZ", "Code postal")),
        Column("city", ("Localité", "Ort", "Lieu", "Ville")),
        Column("language", ("Langue", "Sprache", "Korrespondenzsprache")),
        Column("iban", ("IBAN", "No IBAN", "IBAN-Nr")),
        Column(
            "bank",
            ("Bank IBANname", "Banque", "Bank", "Nom de la banque"),
            note="Mélange noms de banque et codes BIC : à séparer.",
        ),
        Column("ahv_number", ("No AVS", "AVS", "AHV", "AHV-Nr", "No AVS/AHV")),
        Column("ahv_waiver", ("Renonciation AVS", "AHV-Verzicht", "Renonciation")),
    ],
)

PARTICIPANTS = Source(
    key="participants",
    label="Participant-e-s",
    pattern="Participant-e-s_*.xlsx",
    note="Une ligne par inscription : les contacts s'y répètent, c'est normal.",
    columns=[
        Column("last_name", ("Nom", "Name", "Nachname"), required=True),
        Column("first_name", ("Prénom", "Vorname")),
        Column("email", ("Email", "E-Mail", "Courriel", "Mail")),
        Column("phone", ("Téléphone", "Telefon", "Tél.", "Tel")),
        Column("mobile", ("Mobile", "Natel", "Handy", "Portable")),
        Column("street", ("Rue", "Strasse", "Adresse", "Adresse 1")),
        Column("postal_code", ("NPA", "PLZ", "Code postal")),
        Column("city", ("Localité", "Ort", "Lieu", "Ville")),
        Column("language", ("Langue", "Sprache")),
        Column("course_code", ("Cours", "Kurs", "Code", "Code cours", "Kursnummer"), required=True),
        Column("status", ("Statut", "Status", "État", "Zustand")),
        Column(
            "billing_contact",
            ("Facturation", "Contact de facturation", "Rechnungsempfänger", "Rechnung an"),
        ),
        Column("created", ("Créé", "Erstellt", "Date", "Datum")),
        Column("price", ("Prix", "Preis", "Montant", "Betrag")),
        Column("notes", ("Notes", "Notiz", "Remarques", "Bemerkungen")),
    ],
)

MEMBERS = Source(
    key="members",
    label="Membres",
    pattern="membres.xlsx",
    header_row=0,
    skip_rows=(1,),
    note="Deuxième ligne d'en-tête partielle ; une colonne par saison d'envoi.",
    columns=[
        Column("last_name", ("Nom", "Name", "Nachname"), required=True),
        Column("first_name", ("Prénom", "Vorname")),
        Column("email", ("Email", "E-Mail", "Courriel", "Mail")),
        Column("street", ("Rue", "Strasse", "Adresse", "Adresse 1")),
        Column("postal_code", ("NPA", "PLZ", "Code postal")),
        Column("city", ("Localité", "Ort", "Lieu", "Ville")),
        Column("language", ("Langue", "Sprache")),
        Column("membership_type", ("Mitglieder", "Type", "Catégorie", "Mitgliedschaft")),
        Column("function", ("Funktion", "Fonction", "Rôle")),
        Column("since", ("Depuis", "Seit", "Membre depuis", "Eintritt")),
        Column("notes", ("Notes", "Notiz", "Remarques", "Bemerkungen")),
    ],
)

SOURCES: list[Source] = [CATEGORIES, COURSES, TRAINERS, PARTICIPANTS, MEMBERS]

#: Préfixe des colonnes « une par saison » de `membres.xlsx`, transformées en
#: campagnes plutôt qu'en colonnes (voir apps/communications).
PREFIXES_CAMPAGNE = ("programmversand", "programm_versand", "envoi_programme")


@dataclass
class SourceFile:
    """Un export trouvé sur le disque."""

    source: Source
    path: object
    exists: bool = True
    extra: dict = field(default_factory=dict)


def find_sources(directory) -> list[SourceFile]:
    """Localise les exports dans un dossier, sans les ouvrir."""
    from pathlib import Path

    dossier = Path(directory)
    trouves: list[SourceFile] = []
    for source in SOURCES:
        correspondances = sorted(dossier.glob(source.pattern))
        if correspondances:
            # Le plus récent en cas d'exports multiples horodatés.
            trouves.append(SourceFile(source=source, path=correspondances[-1]))
        else:
            trouves.append(SourceFile(source=source, path=dossier / source.pattern, exists=False))
    return trouves
