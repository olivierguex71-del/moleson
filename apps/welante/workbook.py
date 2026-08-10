"""Lecture des classeurs Excel exportés de Welante.

Deux pièges documentés dans l'analyse des exports sont traités ici :

- ``membres.xlsx`` porte une **deuxième ligne d'en-tête** partielle
  (« Mitglieder », « Funktion »…) qu'il faut sauter, sans quoi elle deviendrait
  une ligne de données ;
- les dates sortent parfois en **numéro de série Excel** plutôt qu'en date.

Tout est lu en texte : convertir trop tôt perdrait les zéros de tête d'un NPA et
transformerait un IBAN en notation scientifique. La conversion vient après, dans
`normalizers`, où chaque échec est consigné plutôt que silencieux.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class WorkbookError(RuntimeError):
    """Le classeur est absent, illisible ou vide."""


@dataclass
class Workbook:
    """Un export Welante chargé en mémoire."""

    path: Path
    frame: pd.DataFrame

    @property
    def headers(self) -> list[str]:
        return [str(colonne) for colonne in self.frame.columns]

    @property
    def row_count(self) -> int:
        return len(self.frame)

    def rows(self):
        """Itère sur les lignes, numérotées comme dans le tableur.

        Le numéro rendu est celui qu'Olivier verra en ouvrant le fichier : c'est
        la seule façon utile de désigner une ligne dans un rapport d'anomalies.
        """
        for position, (_, ligne) in enumerate(self.frame.iterrows(), start=2):
            yield position, ligne


def read_workbook(
    path: str | Path,
    *,
    sheet: str | int = 0,
    header_row: int = 0,
    skip_rows: tuple[int, ...] = (),
) -> Workbook:
    """Charge un export en texte brut.

    `skip_rows` désigne des lignes à ignorer **après** l'en-tête — c'est par là
    que se traite la deuxième ligne d'en-tête de `membres.xlsx`.
    """
    chemin = Path(path)
    if not chemin.exists():
        raise WorkbookError(
            f"Export introuvable : {chemin}. Le dossier data/ se recopie à la main "
            "sur chaque machine, il ne transite jamais par Git (nLPD)."
        )

    try:
        frame = pd.read_excel(
            chemin,
            sheet_name=sheet,
            header=header_row,
            skiprows=list(skip_rows) or None,
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:  # openpyxl remonte des erreurs très variées
        raise WorkbookError(f"Lecture impossible de {chemin.name} : {exc}") from exc

    if frame.empty:
        raise WorkbookError(f"{chemin.name} ne contient aucune ligne de données.")

    frame = frame.rename(columns=lambda intitule: str(intitule).strip())
    return Workbook(path=chemin, frame=frame)


def looks_like_second_header(frame: pd.DataFrame) -> bool:
    """Détecte la deuxième ligne d'en-tête de `membres.xlsx`.

    Signe distinctif : une première ligne très creuse, dont les rares valeurs
    ressemblent à des intitulés (courts, sans chiffre) plutôt qu'à des données.
    """
    if frame.empty:
        return False

    premiere = [str(valeur).strip() for valeur in frame.iloc[0].tolist()]
    remplies = [valeur for valeur in premiere if valeur]
    if not remplies or len(remplies) > len(premiere) / 2:
        return False

    return all(len(valeur) < 30 and not any(c.isdigit() for c in valeur) for valeur in remplies)
