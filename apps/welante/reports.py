"""Rapport d'anomalies de migration.

Règle de conception, dictée par la nLPD : **le rapport ne recopie jamais une
valeur du fichier source**. Il désigne un fichier, une ligne, une colonne, et
décrit le problème. Olivier ouvre le classeur à la ligne indiquée.

Un rapport est destiné à être lu, copié dans un message, gardé en trace — il ne
doit pas devenir un second exemplaire des données personnelles.

Le seul cas où une valeur doit sortir est la relecture des découpages
bilingues : elle produit un fichier séparé, écrit dans `data/` (exclu de Git) et
explicitement signalé comme contenant des données.
"""

import csv
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from django.db import DatabaseError, transaction


class Severity:
    """Ce que l'anomalie implique pour la suite."""

    #: La ligne ne peut pas être importée.
    ERROR = "erreur"
    #: La ligne est importée, mais une valeur a été écartée ou devinée.
    WARNING = "avertissement"
    #: La ligne est importée et demande un arbitrage humain (découpage DE/FR…).
    REVIEW = "à relire"


@dataclass(frozen=True)
class Anomaly:
    """Un problème rencontré sur une ligne précise."""

    source: str
    row: int
    column: str
    code: str
    message: str
    severity: str = Severity.WARNING

    def __str__(self) -> str:
        return f"{self.source} ligne {self.row} · {self.column} — {self.message}"


@dataclass
class ImportReport:
    """Ce qu'a produit un import : compteurs et anomalies."""

    source: str
    anomalies: list[Anomaly] = field(default_factory=list)
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0

    def add(
        self,
        *,
        row: int,
        column: str,
        code: str,
        message: str,
        severity: str = Severity.WARNING,
    ) -> None:
        self.anomalies.append(
            Anomaly(
                source=self.source,
                row=row,
                column=column,
                code=code,
                message=message,
                severity=severity,
            )
        )

    @property
    def errors(self) -> list[Anomaly]:
        return [anomalie for anomalie in self.anomalies if anomalie.severity == Severity.ERROR]

    @property
    def to_review(self) -> list[Anomaly]:
        return [anomalie for anomalie in self.anomalies if anomalie.severity == Severity.REVIEW]

    @property
    def counts_by_code(self) -> Counter:
        return Counter(anomalie.code for anomalie in self.anomalies)

    def summary_lines(self) -> list[str]:
        """Résumé lisible en console, sans aucune valeur du fichier source."""
        lignes = [
            f"{self.source} : {self.rows_read} lignes lues, "
            f"{self.rows_imported} importées, {self.rows_skipped} écartées",
        ]
        if not self.anomalies:
            lignes.append("  aucune anomalie")
            return lignes

        for code, nombre in self.counts_by_code.most_common():
            exemple = next(anomalie for anomalie in self.anomalies if anomalie.code == code)
            lignes.append(f"  {nombre:>4} × {code} ({exemple.severity}) — {exemple.message}")
        return lignes

    def write_csv(self, destination: str | Path) -> Path:
        """Écrit les anomalies ligne à ligne, pour traitement méthodique."""
        chemin = Path(destination)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", encoding="utf-8", newline="") as fichier:
            redacteur = csv.writer(fichier, delimiter=";")
            redacteur.writerow(["fichier", "ligne", "colonne", "gravité", "code", "message"])
            for anomalie in self.anomalies:
                redacteur.writerow(
                    [
                        anomalie.source,
                        anomalie.row,
                        anomalie.column,
                        anomalie.severity,
                        anomalie.code,
                        anomalie.message,
                    ]
                )
        return chemin


@contextmanager
def ligne_isolee(rapport: ImportReport, numero: int, colonne: str = "—"):
    """Isole le traitement d'une ligne, pour qu'un refus de la base n'arrête pas tout.

    Une seule ligne trop longue ou en conflit ferait sinon échouer l'import
    entier, sans dire laquelle — après vingt minutes de traitement. Le point de
    sauvegarde permet de consigner l'incident et de poursuivre : à la fin, le
    rapport liste **toutes** les lignes à corriger, pas seulement la première.

    Seule la première ligne du message d'erreur est reprise : PostgreSQL place
    les valeurs fautives dans le `DETAIL`, qui n'a pas sa place dans un rapport
    destiné à circuler (nLPD).
    """
    try:
        with transaction.atomic():
            yield
    except DatabaseError as exc:
        rapport.add(
            row=numero,
            column=colonne,
            code="refus_de_la_base",
            message=str(exc).split("\n")[0].strip(),
            severity=Severity.ERROR,
        )
        rapport.rows_skipped += 1


@dataclass
class ReportSet:
    """L'ensemble des rapports d'une exécution."""

    reports: list[ImportReport] = field(default_factory=list)

    def add(self, report: ImportReport) -> ImportReport:
        self.reports.append(report)
        return report

    @property
    def has_errors(self) -> bool:
        return any(rapport.errors for rapport in self.reports)

    @property
    def total_to_review(self) -> int:
        return sum(len(rapport.to_review) for rapport in self.reports)

    def summary_lines(self) -> list[str]:
        lignes: list[str] = []
        for rapport in self.reports:
            lignes.extend(rapport.summary_lines())
            lignes.append("")
        return lignes
