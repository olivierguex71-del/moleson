"""Normalisation des valeurs sorties de Welante.

Chaque fonction renvoie une valeur propre **ou** `None`, jamais une valeur
approximative : une date mal devinée ou un NPA inventé traverserait la migration
sans bruit et se découvrirait des mois plus tard, sur un courrier retourné.
L'appelant consigne les `None` dans le rapport d'anomalies.
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from apps.core.validators import normalize_iban, validate_iban

#: Excel compte les jours depuis le 30 décembre 1899 (l'année 1900 y est
#: bissextile à tort, décalage que cette origine absorbe).
ORIGINE_EXCEL = date(1899, 12, 30)

#: Bornes de vraisemblance : hors de là, ce n'était pas une date.
ANNEE_MIN, ANNEE_MAX = 1900, 2100

FORMATS_DE_DATE = ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]


def clean_text(valeur: object) -> str:
    """Supprime les espaces superflus, y compris insécables et retours à la ligne."""
    texte = str(valeur or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", texte).strip()


def parse_date(valeur: object) -> date | None:
    """Lit une date, qu'elle soit en numéro de série Excel ou en texte.

    Les exports bruts contiennent les deux formes — la colonne « Créé » sort en
    série, d'autres en texte suisse.
    """
    texte = clean_text(valeur)
    if not texte:
        return None

    if re.fullmatch(r"\d{4,6}(\.0+)?", texte):
        try:
            jour = ORIGINE_EXCEL + timedelta(days=int(float(texte)))
        except (ValueError, OverflowError):
            return None
        return jour if ANNEE_MIN <= jour.year <= ANNEE_MAX else None

    for format_de_date in FORMATS_DE_DATE:
        try:
            jour = datetime.strptime(texte[:10], format_de_date).date()
        except ValueError:
            continue
        return jour if ANNEE_MIN <= jour.year <= ANNEE_MAX else None

    return None


def parse_decimal(valeur: object) -> Decimal | None:
    """Lit un montant, en tolérant l'apostrophe des milliers suisse (1'250.00)."""
    texte = clean_text(valeur).replace("'", "").replace(" ", "").replace("CHF", "")
    if not texte:
        return None
    # Une virgule décimale française devient un point ; un point de milliers
    # accompagné d'une virgule décimale disparaît.
    if "," in texte and "." in texte:
        texte = texte.replace(".", "").replace(",", ".")
    else:
        texte = texte.replace(",", ".")
    try:
        return Decimal(texte)
    except InvalidOperation:
        return None


def parse_int(valeur: object) -> int | None:
    texte = clean_text(valeur)
    correspondance = re.search(r"-?\d+", texte)
    return int(correspondance.group()) if correspondance else None


def parse_int_range(valeur: object) -> tuple[int | None, int | None]:
    """Lit « 5 - 8 » en (5, 8) — la colonne « TN Min-Max » est un texte."""
    texte = clean_text(valeur)
    if not texte:
        return None, None
    nombres = [int(nombre) for nombre in re.findall(r"\d+", texte)]
    if not nombres:
        return None, None
    if len(nombres) == 1:
        return nombres[0], None
    return nombres[0], nombres[1]


def normalize_postal_code(valeur: object) -> str | None:
    """Ramène un NPA à quatre chiffres, en récupérant les zéros perdus par Excel."""
    texte = clean_text(valeur)
    chiffres = re.sub(r"\D", "", texte)
    if not chiffres:
        return None
    if len(chiffres) == 3:
        # Excel a mangé le zéro de tête d'un NPA romand — mais aucun NPA suisse
        # ne commence par zéro : on refuse plutôt que d'en fabriquer un.
        return None
    return chiffres if len(chiffres) == 4 and 1000 <= int(chiffres) <= 9999 else None


def normalize_city(valeur: object) -> str:
    """Corrige les coquilles d'espacement des localités composées.

    « Villars -sur-Glâne » et « Villars- sur-Glâne » deviennent
    « Villars-sur-Glâne » : ces variantes fabriquent de faux doublons.
    """
    texte = clean_text(valeur)
    return re.sub(r"\s*-\s*", "-", texte)


def normalize_phone(valeur: object) -> str:
    """Met un numéro suisse en forme internationale lisible.

    En cas de forme inattendue, la valeur nettoyée est rendue telle quelle : un
    numéro un peu mal formé reste utilisable, contrairement à une date fausse.
    """
    texte = re.sub(r"[^\d+]", "", clean_text(valeur))
    if not texte:
        return ""
    if texte.startswith("00"):
        texte = "+" + texte[2:]
    if texte.startswith("0") and len(texte) == 10:
        texte = "+41" + texte[1:]
    if texte.startswith("+41") and len(texte) == 12:
        return f"+41 {texte[3:5]} {texte[5:8]} {texte[8:10]} {texte[10:]}"
    return texte


def normalize_iban_value(valeur: object) -> tuple[str | None, str]:
    """Normalise et vérifie un IBAN.

    Renvoie `(iban, "")` si la clé de contrôle est bonne, `(None, motif)` sinon —
    un IBAN faux vaut mieux absent que silencieusement enregistré : c'est un
    virement de formateur qui se perdrait.
    """
    compact = normalize_iban(clean_text(valeur))
    if not compact:
        return None, "absent"
    try:
        validate_iban(compact)
    except Exception as exc:  # ValidationError et ses variantes
        motif = getattr(exc, "code", "") or "invalide"
        return None, str(motif)
    return compact, ""


def split_multi(valeur: object, separateur: str = ";") -> list[str]:
    """Découpe une liste de valeurs concaténées (« Langues; Italien; Newsletter »)."""
    return [
        element
        for element in (clean_text(part) for part in str(valeur or "").split(separateur))
        if element
    ]


def parse_category_path(valeur: object) -> tuple[str, str]:
    """Sépare « Parent > Enfant » en ses deux niveaux.

    Une catégorie sans hiérarchie remonte comme parente, sans enfant.
    """
    texte = clean_text(valeur)
    if ">" not in texte:
        return texte, ""
    parent, _, enfant = texte.partition(">")
    return clean_text(parent), clean_text(enfant)


def parse_bool(valeur: object) -> bool:
    """Lit les booléens tels que Welante les exporte (0/1, oui/non, ja/nein, x)."""
    texte = clean_text(valeur).lower()
    return texte in {"1", "true", "vrai", "oui", "ja", "x", "yes", "100%"}


#: Intitulés de langue rencontrés dans les exports. Le mélange est réel : la
#: colonne des intervenants dit « French » et « Allemand » dans le même champ.
LANGUES = {
    "fr": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "französisch": "fr",
    "de": "de",
    "german": "de",
    "allemand": "de",
    "deutsch": "de",
    "alemand": "de",
}


def parse_language(valeur: object, defaut: str = "fr") -> str:
    """Ramène une langue de correspondance à `fr` ou `de`."""
    texte = clean_text(valeur).lower()
    return LANGUES.get(texte, LANGUES.get(texte[:2], defaut))


#: Civilités telles qu'exportées, dans les deux langues.
CIVILITES = {
    "madame": "madam",
    "frau": "madam",
    "mme": "madam",
    "monsieur": "sir",
    "herr": "sir",
    "m": "sir",
    "mr": "sir",
}


def parse_salutation(valeur: object, defaut: str = "neutral") -> str:
    """Lit la civilité déclarée.

    Donnée fournie par la personne, jamais déduite d'un prénom. Une valeur
    inconnue ou absente donne « sans civilité » plutôt qu'une supposition.
    """
    return CIVILITES.get(clean_text(valeur).lower().rstrip("."), defaut)
